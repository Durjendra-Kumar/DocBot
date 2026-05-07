from PyPDF2 import PdfReader

def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def chunk_text(text, size=500):
    return [text[i:i+size] for i in range(0, len(text), size)]