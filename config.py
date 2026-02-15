import os

# Добавляем http:// автоматически, если его нет
raw_es_host = os.getenv('ES_HOST', 'elasticsearch:9200')
if not raw_es_host.startswith(('http://', 'https://')):
    ES_HOST = f'http://{raw_es_host}'
else:
    ES_HOST = raw_es_host

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret')
DOCS_PATH = '/app/docs'
DB_PATH = '/app/db.sqlite'
INDEX_NAME = 'documents'