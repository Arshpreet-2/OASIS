"""Tool: produce a PowerPoint deck. STATE-CHANGING - needs approval.

Title slide, one slide per section, and a closing sources slide naming every
document and page the content came from.
"""

import datetime

from agent.tools_impl._common import OUTPUT_DIR, output_name

_TEMPLATE_NOTE = []




def _resolve_image(name):
    """Find a chart by the name the model used.

    It will usually give the bare filename it saw in an earlier step, not a
    path, so look where charts are written.
    """
    import pathlib

    if not name:
        return ""
    candidates = [pathlib.Path(name),
                  pathlib.Path("outputs") / pathlib.Path(name).name]
    for c in candidates:
        if c.exists() and c.suffix.lower() in (".png", ".jpg", ".jpeg"):
            return str(c)
    return ""


def _normalise(slides):
    """Small models produce slides in several shapes. Accept them all.

    [{"heading": "...", "bullets": [...]}]   the intended form
    [{"title": "...", "points": [...]}]      near misses on key names
    [{"heading": "...", "bullets": "a\nb"}]  bullets as one string
    ["Heading: a; b", ...]                   plain strings
    """
    out = []
    for item in (slides or []):
        if isinstance(item, str):
            head, _, rest = item.partition(":")
            bullets = [b.strip() for b in rest.replace("\n", ";").split(";")
                       if b.strip()]
            out.append({"heading": head.strip() or "Slide",
                        "bullets": bullets})
            continue
        if not isinstance(item, dict):
            continue
        head = (item.get("heading") or item.get("title")
                or item.get("header") or "Slide")
        bl = (item.get("bullets") or item.get("points")
              or item.get("content") or item.get("body") or [])
        if isinstance(bl, str):
            bl = [b.strip() for b in bl.replace(";", "\n").split("\n")
                  if b.strip()]
        entry = {"heading": str(head),
                 "bullets": [str(b) for b in bl if str(b).strip()]}
        # Carry the layout the model chose. Dropping it here silently undid
        # the whole point of showing it the template's layouts.
        lay = item.get("layout") or item.get("slide_layout")
        if lay:
            entry["layout"] = str(lay)
        # A chart already written by write_chart. The file exists on disk;
        # naming it here places it on the slide rather than leaving the deck
        # to describe numbers it could simply show.
        img = (item.get("image") or item.get("chart")
               or item.get("chart_file") or item.get("picture"))
        if img:
            entry["image"] = str(img)
        out.append(entry)
    return out


def profile_layouts(path) -> list:
    """Describe a template's layouts so the model can choose among them.

    The code must not know that "Title Slide" or "Content 2 Column" mean
    anything - the next template will name them differently. Hand the model
    what is actually in the file and let it decide, the same way the table
    schema is handed to it for query_data.
    """
    from pptx import Presentation

    out = []
    for lay in Presentation(path).slide_layouts:
        kinds = {}
        for ph in lay.placeholders:
            k = str(ph.placeholder_format.type).split(" ")[0].lower()
            if k in ("date", "footer", "slide_number"):
                continue                      # furniture, not content slots
            kinds[k] = kinds.get(k, 0) + 1
        out.append({"name": lay.name, "slots": kinds})
    return out


def layouts_for_prompt(profile) -> str:
    """One line per layout, for the model's prompt."""
    lines = []
    for lay in profile:
        slots = ", ".join(f"{n}x {k}" if n > 1 else k
                          for k, n in lay["slots"].items()) or "no content slots"
        lines.append(f'  "{lay["name"]}" - {slots}')
    return "\n".join(lines)


def _pick_layouts(prs):
    """Find a title layout and a title+body layout in someone else's template.

    Templates do not agree on layout order, so never choose by index. Names are
    conventional enough to try first ("Title Slide", "Title and Content"), and
    placeholder shape is the fallback when a template uses its own names.
    Returns (title_layout, body_layout); either may fall back to the other.
    """
    # Normalise separators - templates write "Title Slide", "TITLE_SLIDE" and
    # "Title-Slide" for the same thing.
    def norm(t):
        return " ".join(str(t).lower().replace("_", " ").replace("-", " ").split())

    by_name = {norm(lay.name): lay for lay in prs.slide_layouts}

    def named(*wanted):
        for w in wanted:
            for name, lay in by_name.items():
                if w in name:
                    return lay
        return None

    title_layout = named("title slide", "title only", "section header")
    body_layout = named("title and content", "content with caption",
                        "title and body", "content")

    if body_layout is None or title_layout is None:
        # Fall back to shape: a body layout has a title placeholder (idx 0)
        # and at least one other content placeholder below it.
        for lay in prs.slide_layouts:
            # Match on placeholder TYPE, not index. A template built by another
            # tool may number its placeholders 102/103 rather than 0/1.
            kinds = [norm(ph.placeholder_format.type)
                     for ph in lay.placeholders]
            has_title = any("title" in k for k in kinds)
            has_body = any(("body" in k or "object" in k or "content" in k)
                           for k in kinds)
            if has_title and has_body and body_layout is None:
                body_layout = lay
            elif has_title and not has_body and title_layout is None:
                title_layout = lay

    return title_layout or body_layout, body_layout or title_layout


def _from_template(path, title, subtitle, slides, sources, author,
                   title_hint=None, sources_hint=None):
    """Build the deck inside the user's own template so the master, fonts,
    colours and logo come along. Returns a Presentation, or None if the
    template has no layout we can fill."""
    from pptx import Presentation

    prs = Presentation(path)

    # A template usually carries example slides. Opening it keeps them, so a
    # generated deck would start with someone else's sample content. Drop them
    # - the layouts and the master are what we came for.
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        rId = sld_id.get("{http://schemas.openxmlformats.org/officeDocument/"
                         "2006/relationships}id")
        prs.part.drop_rel(rId)
        sld_id_lst.remove(sld_id)

    title_layout, body_layout = _pick_layouts(prs)
    if body_layout is None:
        return None

    by_name = {lay.name.strip().lower(): lay for lay in prs.slide_layouts}

    def chosen(wanted, default):
        """The layout the model named, if the template has it."""
        if not wanted:
            return default
        return by_name.get(str(wanted).strip().lower(), default)

    def place_image(sl, path, body_ph):
        """Put a chart on the slide, in the body placeholder's space.

        Scaled to fit rather than stretched: a distorted chart misreads, and
        the axis labels are the part that matters.
        """
        from PIL import Image

        here = _resolve_image(path)
        if not here:
            return False
        if body_ph is not None:
            left, top = body_ph.left, body_ph.top
            avail_w, avail_h = body_ph.width, body_ph.height
            sl.shapes._spTree.remove(body_ph._element)
        else:
            left, top = Inches(0.9), Inches(1.9)
            avail_w = prs.slide_width - Inches(1.8)
            avail_h = prs.slide_height - Inches(2.6)
        with Image.open(here) as im:
            ratio = im.height / im.width
        width = avail_w
        height = int(width * ratio)
        if height > avail_h:
            height = avail_h
            width = int(height / ratio)
        sl.shapes.add_picture(here, left + (avail_w - width) // 2, top,
                              width=width, height=height)
        return True

    def fill(layout, heading, lines, image=None):
        sl = prs.slides.add_slide(layout)
        title_ph = body = None
        for ph in sl.placeholders:
            kind = str(ph.placeholder_format.type).lower()
            if "title" in kind and title_ph is None:
                title_ph = ph
            elif body is None:
                body = ph
        # Fall back to position if the template names nothing recognisably:
        # the topmost placeholder is the heading.
        if title_ph is None and sl.placeholders:
            ordered = sorted(sl.placeholders, key=lambda p: p.top or 0)
            title_ph = ordered[0]
            body = ordered[1] if len(ordered) > 1 else None
        if title_ph is not None:
            title_ph.text = heading
        if image and place_image(sl, image, body):
            return sl
        if body is not None and lines:
            tf = body.text_frame
            tf.text = lines[0]
            for extra in lines[1:]:
                tf.add_paragraph().text = extra
        elif body is not None:
            body.text = ""
        return sl

    fill(chosen(title_hint, title_layout), title,
         [x for x in (subtitle, author) if x])
    for sl in slides:
        fill(chosen(sl.get("layout"), body_layout), sl["heading"],
             sl["bullets"], sl.get("image"))
    if sources:
        fill(chosen(sources_hint, body_layout), "Sources",
             [f'{s["document"]}  p.{s["page"]}' for s in sources])
    return prs


def tool_write_pptx(title: str, subtitle: str = "", slides: list = None,
                    sources: list = None, filename: str = None,
                    author: str = "", template_path: str = None,
                    title_layout: str = None, sources_layout: str = None,
                    **_ignored):
    """Produce a presentation. STATE-CHANGING - needs approval first.

    slides is a list of {"heading": str, "bullets": [str, ...]}
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    INK = RGBColor(0x1A, 0x16, 0x30)
    MUTED = RGBColor(0x5F, 0x57, 0x80)
    ACCENT = RGBColor(0x6A, 0x57, 0xC4)

    slides_n = _normalise(slides)

    # The user supplied their own deck as a template. python-pptx inherits the
    # master directly, so the branding is exact rather than approximated - far
    # better than describing a layout to the model in words.
    if template_path:
        try:
            built = _from_template(template_path, title, subtitle, slides_n,
                                   sources or [], author,
                                   title_hint=title_layout,
                                   sources_hint=sources_layout)
            if built is not None:
                name = output_name("deck", "pptx", filename)
                built.save(OUTPUT_DIR / name)
                return {"file": name, "path": str(OUTPUT_DIR / name),
                        "slides": len(built.slides), "from_template": True,
                        "message": f"{name} written using your template "
                                   f"({len(built.slides)} slides)."}
        except Exception as e:
            # A template we cannot use is not a reason to fail - fall through
            # to the house layout and say what happened.
            _TEMPLATE_NOTE.append(str(e))

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def textbox(slide, x, y, w, h, text, size, bold=False, colour=INK):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.runs[0].font.size = Pt(size)
        p.runs[0].font.bold = bold
        p.runs[0].font.color.rgb = colour
        return tf

    # --- title slide
    s0 = prs.slides.add_slide(blank)
    textbox(s0, 0.9, 2.5, 11.5, 1.4, title or "Report", 40, True)
    if subtitle:
        textbox(s0, 0.9, 3.9, 11.5, 0.8, subtitle, 17, False, MUTED)
    footer = "Prepared on premises from plant documentation"
    if author:
        footer += f"  ·  {author}"
    textbox(s0, 0.9, 6.5, 11.5, 0.5, footer, 11, False, MUTED)

    # --- content slides
    for item in _normalise(slides):
        sl = prs.slides.add_slide(blank)
        textbox(sl, 0.9, 0.7, 11.5, 0.9, item.get("heading", ""), 28, True)

        tb = sl.shapes.add_textbox(Inches(0.9), Inches(1.9),
                                   Inches(11.5), Inches(4.6))
        tf = tb.text_frame
        tf.word_wrap = True
        first = True
        for b in item.get("bullets", []):
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.text = str(b)
            p.space_after = Pt(14)
            p.runs[0].font.size = Pt(16)
            p.runs[0].font.color.rgb = INK

    if len(prs.slides._sldIdLst) == 1 and subtitle:
        sl = prs.slides.add_slide(blank)
        textbox(sl, 0.9, 0.7, 11.5, 0.9, "Summary", 28, True)
        tb = sl.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(11.5), Inches(4))
        tb.text_frame.word_wrap = True
        p = tb.text_frame.paragraphs[0]
        p.text = subtitle
        p.runs[0].font.size = Pt(16)

    # --- sources slide
    if sources:
        sl = prs.slides.add_slide(blank)
        textbox(sl, 0.9, 0.7, 11.5, 0.9, "Sources", 28, True, ACCENT)
        tb = sl.shapes.add_textbox(Inches(0.9), Inches(1.9),
                                   Inches(11.5), Inches(4.6))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, src in enumerate(sources, 1):
            pg = f", page {src['page']}" if src.get("page") is not None else ""
            p = tf.paragraphs[0] if i == 1 else tf.add_paragraph()
            p.text = f"[{i}]  {src['document']}{pg}"
            p.space_after = Pt(10)
            p.runs[0].font.size = Pt(13)
            p.runs[0].font.color.rgb = MUTED

    name = output_name("deck", "pptx", filename)
    path = OUTPUT_DIR / name
    prs.save(path)
    return {"file": name, "path": str(path), "slides": len(prs.slides._sldIdLst)}
