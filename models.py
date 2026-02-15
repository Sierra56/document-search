import sqlite3
import json
from datetime import datetime
from elasticsearch import Elasticsearch

from config import ES_HOST, INDEX_NAME, DB_PATH

es = Elasticsearch([ES_HOST])

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT UNIQUE,
            added_date TEXT,
            status TEXT DEFAULT 'indexing'
        )
    ''')
    conn.commit()
    conn.close()

def get_doc_status(filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT status, added_date FROM documents WHERE filename = ?', (filename,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'status': row[0], 'added_date': row[1]}
    return None

def update_doc_status(filename, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        'INSERT OR REPLACE INTO documents (filename, added_date, status) VALUES (?, ?, ?)',
        (filename, now, status)
    )
    conn.commit()
    conn.close()

def list_docs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT filename, added_date, status FROM documents ORDER BY added_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return [{'filename': row[0], 'added_date': row[1], 'status': row[2]} for row in rows]

def delete_doc(filename):
    es.delete(index=INDEX_NAME, id=filename, ignore=[404])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM documents WHERE filename = ?', (filename,))
    conn.commit()
    conn.close()
    import os
    from config import DOCS_PATH
    filepath = os.path.join(DOCS_PATH, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

def create_index():
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body={
            'mappings': {
                'properties': {
                    'content': {'type': 'text', 'analyzer': 'standard'},
                    'filename': {'type': 'keyword'},
                    'added_date': {'type': 'date'}
                }
            }
        })