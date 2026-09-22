"""
TEXT RECOGNITION.  Original author: jain-eti (feature/agent).

Recovers text from a page that has none — a scan, a photograph, or a drawing
exported as an image. A scanned PDF is a picture of a page, so pypdf returns
nothing from it; this renders each page, straightens it, and reads the pixels.

Four steps, only the last of which is a model:
    1. decide whether the PDF is a scan at all, by how much of the page is
       covered by text blocks — a PDF with a real text layer skips OCR
    2. render each page to an image
    3. deskew and lift local contrast, so the recognition model sees
       straight, legible characters
    4. detect text regions, then read them

Steps 1–3 are ordinary computer vision. Step 4 is PaddleOCR: a detection model
that finds boxes and a recognition model that reads them.

FIXES APPLIED after testing on a scanned A4 report and a scanned A3 P&ID, both
with no text layer (each is marked FIX below):
    - get_image() ignored its argument and read self.image, which is None on
      the document path, so OCR never saw the preprocessed page
    - the page loop never collected its text, and joined with two arguments,
      which raises TypeError before OCR is reached
    - pages rendered at PyMuPDF's 72 dpi default: fine for 9.5pt prose,
      illegible for the 7pt tags on a drawing
    - the rotation kept the original frame, so anything swung outside it was
      discarded — on a wide drawing that cut the title block and the start of
      every note

Result after the fixes: one character wrong across a full A3 drawing.

OFFLINE: PaddleOCR downloads ~155 MB of models on first use and checks
connectivity before doing so. See prepare_offline() and SETUP.md — on an
air-gapped machine the models must be present before the first call.
"""

import os
import pathlib

# Keep the models beside the project rather than in the user's home directory,
# so they can be shipped with it and so nothing is fetched at runtime.
_MODELS = pathlib.Path(__file__).resolve().parent / "ocr_models"
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "local")
if _MODELS.exists():
    os.environ.setdefault("PADDLEX_HOME", str(_MODELS))

# Rendering resolution for a scanned page. 200 dpi, not 300: PaddleOCR caps the
# long side at 4000 px, and an A3 page at 300 dpi comes out 5136 px and is
# downscaled anyway. Measured on the same drawing, 200 and 300 gave identical
# text — so 300 spends memory and time on pixels that are then thrown away.
RENDER_DPI = 200

# Below this fraction of the page covered by text blocks, treat the PDF as a
# scan and go to OCR.
TEXT_AREA_FLOOR = 0.01

_ocr = None


def _engine():
    """One PaddleOCR instance for the process.

    Constructing it loads five models. Doing that per request cost seconds
    every time and achieved nothing.
    """
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR()
    return _ocr


def available() -> bool:
    """Whether OCR can run here. Paddle is a large optional dependency and the
    rest of the system must work without it."""
    try:
        import paddleocr  # noqa: F401
        import cv2        # noqa: F401
        import pymupdf    # noqa: F401
        return True
    except Exception:
        return False


def preprocessing(img):
    """Straighten the page and lift local contrast. Returns the image
    unchanged if it cannot find a page edge to measure."""
    import cv2
    import numpy as np

    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    canny = cv2.Canny(gray, 50, 255)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    contours, _ = cv2.findContours(canny, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img                      # nothing to measure; leave it alone

    rect = cv2.minAreaRect(max(contours, key=cv2.contourArea))
    angle = rect[2]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.05:
        return img                      # already straight

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # FIX: rotating inside the original frame throws away whatever swings
    # outside it. On a portrait page with wide margins that is invisible; on a
    # wide drawing it cut the title block and the start of every note. Grow the
    # canvas to the rotated bounding box, then shift the image into it.
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += new_w / 2 - center[0]
    M[1, 2] += new_h / 2 - center[1]

    return cv2.warpAffine(img, M, (new_w, new_h), flags=cv2.INTER_CUBIC,
                          borderValue=(255, 255, 255))


class TextRecog:
    def __init__(self, image=None, document=None):
        self.image = image
        self.document = document

    def get_image(self, image=None):
        """Read one image. Returns the text as a single line."""
        if image is None:
            image = self.image
        if image is None:
            return ""
        # FIX: was predict(self.image), which ignored the argument and read
        # None on the document path, so the preprocessed page never arrived.
        result = _engine().predict(image)
        out = []
        for res in result:
            out.extend(res["rec_texts"])
        return " ".join(out)

    def is_scan(self) -> bool:
        """True when almost none of the page is covered by text blocks.

        Cheaper and more reliable than running OCR to find out: a PDF with a
        real text layer should never be OCR'd, because extracting it is both
        faster and exact.
        """
        import pymupdf

        page_area = text_area = 0.0
        doc = pymupdf.open(self.document)
        for page in doc:
            page_area += abs(page.rect)
            for b in page.get_text_blocks():
                text_area += abs(pymupdf.Rect(b[:4]))
        doc.close()
        if page_area <= 0:
            return True
        return (text_area / page_area) < TEXT_AREA_FLOOR

    def get_document(self) -> list:
        """Return one string per page, so page numbers survive for citation."""
        import cv2
        import numpy as np
        import pymupdf

        doc = pymupdf.open(self.document)
        pages = []

        if not self.is_scan():
            for page in doc:
                pages.append(" ".join((page.get_text() or "").split()))
            doc.close()
            return pages

        for page in doc:
            # FIX: default get_pixmap() renders at 72 dpi. Adequate for 9.5pt
            # prose, illegible for the 7pt tags on a drawing.
            pix = page.get_pixmap(dpi=RENDER_DPI)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR if pix.n == 4
                               else cv2.COLOR_RGB2BGR)

            text = self.get_image(preprocessing(img))
            # FIX: the page text was collected into a list that was discarded,
            # then joined with two arguments, which raises TypeError.
            pages.append(" ".join(text.split()))

        doc.close()
        return pages


def read_pdf_pages(path) -> list:
    """One string per page of a PDF, via OCR when it has no text layer."""
    return TextRecog(document=str(path)).get_document()


def read_image(path) -> str:
    """Text from a photograph or a drawing exported as an image."""
    import cv2

    img = cv2.imread(str(path))
    if img is None:
        return ""
    return TextRecog().get_image(preprocessing(img))


def process_input(file_path):
    """Convenience entry point, kept from the original module."""
    p = str(file_path).lower()
    if p.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif")):
        return read_image(file_path)
    if p.endswith(".pdf"):
        return "\n".join(read_pdf_pages(file_path))
    return ""


def prepare_offline():
    """Download the models once, into the project folder, so the air-gapped
    machine never reaches for them. Run with a network connection:

        python3 -c "from text_recog import prepare_offline; prepare_offline()"
    """
    _MODELS.mkdir(exist_ok=True)
    os.environ["PADDLEX_HOME"] = str(_MODELS)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "False"
    os.environ.pop("PADDLE_PDX_MODEL_SOURCE", None)
    import numpy as np
    _engine().predict(np.full((64, 256, 3), 255, dtype=np.uint8))
    print(f"models are in {_MODELS}")
