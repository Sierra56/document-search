import os, time, hashlib
from elasticsearch import Elasticsearch
from docx import Document
import pdfplumber
from datetime import datetime

ES = Elasticsearch(os.getenv("ES_HOST"))
INDEX = "documents"
DOCS_DIR = "/docs"

def extract_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            text += p.extract_text() or ""
    return text

def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def run():
    ES.indices.create(index=INDEX, ignore=400)
    processed = set()

    while True:
        for root, _, files in os.walk(DOCS_DIR):
            for f in files:
                if not f.lower().endswith((".pdf", ".docx")):
                    continue
                path = os.path.join(root, f)
                h = file_hash(path)
                if h in processed:
                    continue

                try:
                    text = extract_docx(path) if f.endswith("docx") else extract_pdf(path)
                    status = "indexed"
                except Exception:
                    text = ""
                    status = "error"

                ES.index(index=INDEX, document={
                    "filename": f,
                    "path": path,
                    "content": text,
                    "status": status,
                    "indexed_at": datetime.utcnow().isoformat()
                })

                processed.add(h)
        time.sleep(300)

if __name__ == "__main__":
    run()