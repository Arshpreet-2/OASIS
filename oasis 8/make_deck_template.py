"""House deck template for OASIS.

Palette and structure follow a deck the user supplied; the file itself is not
reused, because its master carries another company's logo and every generated
deck would have inherited it. Colours and layout are not protected - a logo is.

The design lives in the MASTER and LAYOUTS. python-pptx builds a deck by adding
slides from a template's layouts and never copies its slides, so a design drawn
on slides looks right in the template and vanishes in anything generated from
it.
"""
import copy

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

ORANGE  = RGBColor(0xF6, 0x8F, 0x1F)
CRIMSON = RGBColor(0xCA, 0x48, 0x51)
HEAD    = RGBColor(0xDA, 0x19, 0x5C)
SLATE   = RGBColor(0x43, 0x53, 0x65)
INK     = RGBColor(0x2D, 0x2D, 0x2D)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)

COMPANY = "Mangalore Refinery and Petrochemicals Limited"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
W, H = prs.slide_width, prs.slide_height


def gradient_panel(shapes, left, top, width, height):
    """Orange to crimson, the diagonal from the source deck."""
    s = shapes.add_shape(1, left, top, width, height)
    s.line.fill.background(); s.shadow.inherit = False
    spPr = s._element.spPr
    for tag in ("a:solidFill", "a:noFill"):
        el = spPr.find(qn(tag))
        if el is not None:
            spPr.remove(el)
    xml = (
        '<a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'rotWithShape="1"><a:gsLst>'
        '<a:gs pos="0"><a:srgbClr val="F68F1F"/></a:gs>'
        '<a:gs pos="55000"><a:srgbClr val="DE7944"/></a:gs>'
        '<a:gs pos="100000"><a:srgbClr val="DA195C"/></a:gs>'
        '</a:gsLst><a:lin ang="2700000" scaled="1"/></a:gradFill>')
    from pptx.oxml import parse_xml
    spPr.insert(2, parse_xml(xml))
    return s


def brand(prs):
    master = prs.slide_master

    donor = Presentation()
    donor.slide_width, donor.slide_height = W, H
    scratch = donor.slides.add_slide(donor.slide_layouts[6])

    foot = scratch.shapes.add_textbox(Inches(0.75), H - Inches(0.5),
                                      Inches(9.0), Inches(0.3))
    p = foot.text_frame.paragraphs[0]
    p.text = COMPANY
    p.font.size = Pt(8.5); p.font.color.rgb = SLATE; p.font.name = "Arial"

    rule = scratch.shapes.add_shape(1, Inches(0.75), Inches(1.5),
                                    Inches(1.5), Pt(3.5))
    rule.fill.solid(); rule.fill.fore_color.rgb = ORANGE
    rule.line.fill.background(); rule.shadow.inherit = False

    furniture = [foot._element, rule._element]

    mf = master.background.fill
    mf.solid(); mf.fore_color.rgb = WHITE

    for layout in master.slide_layouts:
        lf = layout.background.fill
        lf.solid(); lf.fore_color.rgb = WHITE
        tree = layout.shapes._spTree
        for el in furniture:
            tree.append(copy.deepcopy(el))

    # Alignment and type are inherited from the master's own placeholders;
    # setting them per layout alone leaves titles centred.
    for holder in (master, *master.slide_layouts):
        for ph in holder.placeholders:
            kind = str(ph.placeholder_format.type).lower()
            for para in ph.text_frame.paragraphs:
                para.alignment = PP_ALIGN.LEFT
                para.font.name = "Arial"
                if "title" in kind:
                    para.font.size = Pt(34); para.font.bold = True
                    para.font.color.rgb = HEAD
                else:
                    para.font.size = Pt(17); para.font.color.rgb = INK


def head(slide, text):
    """A slide heading in house style.

    Set on the slide rather than left to inherit: PowerPoint and LibreOffice
    disagree about how far a master's title style reaches, and a heading that
    centres in one and not the other is not a template.
    """
    t = slide.shapes.title
    t.text = text
    t.left, t.top, t.width, t.height = (Inches(0.75), Inches(0.45),
                                        Inches(11.8), Inches(0.95))
    for para in t.text_frame.paragraphs:
        para.alignment = PP_ALIGN.LEFT
        para.font.size = Pt(32); para.font.bold = True
        para.font.color.rgb = HEAD; para.font.name = "Arial"
    return t


brand(prs)

# ---------- 1. cover ------------------------------------------------------
s = prs.slides.add_slide(prs.slide_layouts[0])
gradient_panel(s.shapes, Inches(6.4), 0, W - Inches(6.4), H)
t = s.shapes.title
t.text = "Equipment Reliability Review"
t.left, t.top, t.width, t.height = Inches(0.75), Inches(2.4), Inches(5.2), Inches(2.0)
for para in t.text_frame.paragraphs:
    para.font.size = Pt(34); para.font.bold = True
    para.font.color.rgb = INK; para.alignment = PP_ALIGN.LEFT
t.text_frame.word_wrap = True
sub = s.placeholders[1]
sub.left, sub.top, sub.width = Inches(0.78), Inches(6.2), Inches(5.2)
sub.text = "P-101 Crude Charge Pump  ·  16 September 2026"
for para in sub.text_frame.paragraphs:
    para.font.size = Pt(13); para.font.bold = True
    para.font.color.rgb = INK; para.alignment = PP_ALIGN.LEFT

# ---------- 2. content ----------------------------------------------------
s = prs.slides.add_slide(prs.slide_layouts[1])
head(s, "Findings")
body = s.placeholders[1]
body.left, body.top, body.width, body.height = (Inches(0.75), Inches(1.95),
                                                Inches(11.8), Inches(4.5))
tf = body.text_frame; tf.clear()
for i, line in enumerate([
        "Seal failure interval has fallen from 246 days to 94 days",
        "Flush line strainer found 60 percent blocked with scale",
        "Seal faces scored, consistent with dry running",
        "Flush differential pressure not recorded before September 2025"]):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.text = line; p.font.size = Pt(18); p.font.color.rgb = INK
    p.space_after = Pt(13)

# ---------- 3. chart ------------------------------------------------------
s = prs.slides.add_slide(prs.slide_layouts[5])
head(s, "Work orders by type")
ph = s.shapes.add_shape(1, Inches(0.75), Inches(1.95), Inches(11.8), Inches(4.3))
ph.fill.solid(); ph.fill.fore_color.rgb = RGBColor(0xF4, 0xF5, 0xF7)
ph.line.color.rgb = RGBColor(0xE2, 0xE5, 0xEA); ph.shadow.inherit = False
tfx = ph.text_frame; tfx.text = "chart goes here"
tfx.paragraphs[0].alignment = PP_ALIGN.CENTER
tfx.paragraphs[0].font.size = Pt(13); tfx.paragraphs[0].font.color.rgb = SLATE

# ---------- 4. a number ---------------------------------------------------
s = prs.slides.add_slide(prs.slide_layouts[6])
gradient_panel(s.shapes, 0, 0, Inches(0.55), H)
tb = s.shapes.add_textbox(Inches(1.4), Inches(2.5), Inches(10.5), Inches(2.2))
f = tb.text_frame
p = f.paragraphs[0]; p.text = "Rs. 8,58,500"
p.font.size = Pt(68); p.font.bold = True; p.font.color.rgb = HEAD
p2 = f.add_paragraph(); p2.text = "breakdown maintenance, 2024 to 2026"
p2.font.size = Pt(19); p2.font.color.rgb = SLATE

# ---------- 5. ending -----------------------------------------------------
s = prs.slides.add_slide(prs.slide_layouts[5])
gradient_panel(s.shapes, 0, H - Inches(0.28), W, Inches(0.28))
head(s, "Recommendation")
tb = s.shapes.add_textbox(Inches(0.75), Inches(1.95), Inches(11.8), Inches(3.6))
f = tb.text_frame; f.word_wrap = True
for i, line in enumerate([
        "Clean the flush line strainer and restore Plan 32 flush",
        "Record flush differential pressure before every start",
        "Re-inspect at 60 days rather than at failure"]):
    p = f.paragraphs[0] if i == 0 else f.add_paragraph()
    p.text = line; p.font.size = Pt(18); p.font.color.rgb = INK
    p.space_after = Pt(14)

prs.save("house_template.pptx")
print("written")
