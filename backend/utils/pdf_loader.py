
import fitz
def extract_bangla_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        text = page.get_text("text")
        full_text += text + "\n"
    return full_text
