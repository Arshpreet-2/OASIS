"""Generate the organisation's document templates. Run: python make_templates.py

These live in corpus/ like any other document. The agent searches for them
before writing, so the plant controls its own formats - upload a new template
through the Documents tab and the system starts following it.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

OUT = "corpus"
os.makedirs(OUT, exist_ok=True)
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=14, alignment=0,
                    spaceAfter=4, fontName="Helvetica-Bold")
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=10.5, spaceBefore=10,
                    spaceAfter=3, fontName="Helvetica-Bold")
B = ParagraphStyle("B", parent=ss["Normal"], fontSize=9.5, leading=13.5, spaceAfter=4)
S = ParagraphStyle("S", parent=ss["Normal"], fontSize=7.5, leading=10,
                   textColor=colors.HexColor("#666666"))

NOTE = ("SYNTHETIC DOCUMENT - created for a Smart India Hackathon prototype "
        "demonstration. Not real plant data.")


def build(name, title, subtitle, blocks):
    s = [Paragraph(title, H1), Paragraph(subtitle, B), Paragraph(NOTE, S),
         Spacer(1, 8)]
    for head, lines in blocks:
        s.append(Paragraph(head, H2))
        for ln in lines:
            s.append(Paragraph(ln, B))
    SimpleDocTemplate(os.path.join(OUT, name), pagesize=A4,
                      leftMargin=20*mm, rightMargin=20*mm,
                      topMargin=18*mm, bottomMargin=18*mm,
                      title=title).build(s)
    return name


build("template_approval_note.pdf",
      "Standard Template &mdash; Approval Note",
      "Form MNT-AN Rev. 3. All approval notes shall follow this structure.",
      [("1. Heading", [
          "Title in the form: Approval Note &mdash; [equipment tag] [work]",
          "Reference number, date, and the name of the person preparing it."]),
       ("2. Background", [
          "Two or three sentences on the equipment and why the note is raised. "
          "State the work order number and the date of the triggering event."]),
       ("3. Findings", [
          "What was observed, as short numbered points. Each finding must cite "
          "the source document and page it came from. State measured values "
          "against their required values."]),
       ("4. Assessment", [
          "One paragraph attributing the cause. Distinguish the immediate cause "
          "from the underlying cause. Reference any trend in the maintenance "
          "history."]),
       ("5. Recommendation", [
          "Numbered actions, each one specific and assignable. Include part "
          "numbers where a replacement is proposed, and the revised interval "
          "where a change of frequency is proposed."]),
       ("6. Cost and Downtime", [
          "Estimated cost in Rs. and estimated downtime in hours. Where a "
          "figure is not known, say so rather than omitting the line."]),
       ("7. Approval", [
          "A closing line requesting approval from the named authority.",
          "Prepared by / Reviewed by / Approved by, each with a date."])])

build("template_letter.pdf",
      "Standard Template &mdash; Letter and Internal Email",
      "Form ADM-LT Rev. 2. Applies to internal correspondence and external letters.",
      [("1. Subject line", [
          "One line, specific. Name the equipment or matter and the purpose. "
          "Avoid generic subjects such as 'Update' or 'Issue'."]),
       ("2. Greeting", [
          "Address the recipient by role or name. Internal correspondence may "
          "use 'Dear [name]'; external letters use the full form."]),
       ("3. Opening paragraph", [
          "State the purpose in the first sentence. The reader should know why "
          "they received this before the second paragraph."]),
       ("4. Body", [
          "Two or three short paragraphs. One idea each. Cite the source "
          "document and page for any figure quoted. Do not exceed one page."]),
       ("5. Recommendation or request", [
          "State plainly what is being asked of the recipient, and by when."]),
       ("6. Closing", [
          "A sign-off, the sender's name, designation and department.",
          "List any enclosures below the signature."])])

build("template_report.pdf",
      "Standard Template &mdash; Technical Report",
      "Form ENG-RP Rev. 4. Applies to inspection, failure analysis and study reports.",
      [("1. Title block", [
          "Report title, reference number, date, author and reviewer."]),
       ("2. Summary", [
          "Five lines at most. The finding and the recommendation. A reader "
          "who stops here should still know what to do."]),
       ("3. Scope", [
          "What was examined, over what period, and what was excluded."]),
       ("4. Findings", [
          "Numbered. Each cites its source document and page. Measured values "
          "are given against their specified values, with units."]),
       ("5. Analysis", [
          "How the findings connect. State the cause and the evidence for it. "
          "Where evidence is incomplete, say so."]),
       ("6. Recommendations", [
          "Numbered and assignable, each with an owner and a due date."]),
       ("7. References", [
          "Every document relied upon, with its revision and date."])])

print("written to", OUT + "/")
for f in sorted(os.listdir(OUT)):
    if f.startswith("template_"):
        print("  ", f)
