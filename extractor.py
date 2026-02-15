import time
import os

from config import DOCS_PATH
from models import init_db, create_index, get_doc_status
from utils import index_doc

init_db()
create_index()

SUPPORTED_EXTENSIONS = ('.pdf', '.docx', '.rtf')


def scan_and_index():
    for entry in os.scandir(DOCS_PATH):
        if not entry.is_file():
            continue

        filename = entry.name
        if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
            continue

        status_info = get_doc_status(filename)
        if status_info is None or status_info['status'] in ('indexing', 'error'):
            print(f"→ Обрабатываем: {filename}")
            index_doc(filename)


if __name__ == '__main__':
    print("Extractor запущен. Сканирование каждые 30 секунд.")
    print(f"Поддерживаемые форматы: {', '.join(SUPPORTED_EXTENSIONS)}")

    while True:
        try:
            scan_and_index()
        except Exception as e:
            print(f"Ошибка в цикле extractor: {e}")
        time.sleep(30)