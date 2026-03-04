from pypdf import PdfReader
from io import BytesIO

def extract_text_per_page(pdf_bytes: bytes) -> list[dict]:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for i, p in enumerate(reader.pages):
        txt = (p.extract_text() or "").strip()
        pages.append({"page": i+1, "text": txt})
    return pages
