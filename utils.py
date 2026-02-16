import os
import pdfplumber
from docx import Document
from striprtf.striprtf import rtf_to_text
from datetime import datetime
import shutil  # ← добавлен для перемещения файлов

from config import DOCS_PATH, INDEX_NAME
from models import update_doc_status, es

INDEXED_PATH = os.path.join(DOCS_PATH, 'indexed')

# Создаём папку indexed при первом запуске, если её нет
if not os.path.exists(INDEXED_PATH):
    os.makedirs(INDEXED_PATH)

def extract_text(filename):
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

        # Перемещаем файл в indexed после успешной индексации
        src = os.path.join(DOCS_PATH, filename)
        dst = os.path.join(INDEXED_PATH, filename)
        shutil.move(src, dst)
        print(f"Успешно проиндексирован и перемещён: {filename} → {dst}")

        return True
    except Exception as e:
        print(f"Ошибка индексации {filename}: {type(e).__name__} - {str(e)}")
        update_doc_status(filename, 'error')
        return False