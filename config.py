import os

ES_HOST = os.getenv('ES_HOST', 'localhost:9200')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret')
DOCS_PATH = '/app/docs'
DB_PATH = '/app/db.sqlite'
INDEX_NAME = 'documents'