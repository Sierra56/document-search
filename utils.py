import os
import pdfplumber
from docx import Document
from striprtf.striprtf import rtf_to_text
from datetime import datetime

from config import DOCS_PATH, INDEX_NAME
from models import update_doc_status, es

def extract_text(filename):
    """
    Извлекает текст из поддерживаемых файлов.
    Поддерживаются только: .pdf, .docx, .rtf
    """
    filepath = os.path.join(DOCS_PATH, filename)
    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    text = None

    try:
        if ext == '.pdf':
            with pdfplumber.open(filepath) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(pages_text)

        elif ext == '.docx':
            doc = Document(filepath)
            text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())

        elif ext == '.rtf':
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                rtf_content = f.read()
            text = rtf_to_text(rtf_content)

        if text is not None and text.strip():
            return text.strip()
        else:
            return None

    except Exception as e:
        print(f"Ошибка извлечения текста из {filename}: {type(e).__name__} - {str(e)}")
        return None


def index_doc(filename):
    update_doc_status(filename, 'indexing')

    text = extract_text(filename)
    if text is None or not text.strip():
        update_doc_status(filename, 'error')
        return False

    try:
        doc_body = {
            'filename': filename,
            'content': text,
            'added_date': datetime.utcnow().isoformat() + 'Z'
        }
        es.index(index=INDEX_NAME, id=filename, body=doc_body)
        update_doc_status(filename, 'indexed')
        print(f"Успешно проиндексирован: {filename}")
        return True
    except Exception as e:
        print(f"Ошибка индексации {filename}: {type(e).__name__} - {str(e)}")
        update_doc_status(filename, 'error')
        return False