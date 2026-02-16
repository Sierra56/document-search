import sqlite3
from datetime import datetime
from elasticsearch import Elasticsearch

from config import ES_HOST, INDEX_NAME, DB_PATH

es = Elasticsearch([ES_HOST])

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Основная таблица документов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT UNIQUE,
            added_date TEXT,
            status TEXT DEFAULT 'indexing'
        )
    ''')
    
    # Новая таблица для истории поиска
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            ip_address TEXT,
            timestamp TEXT
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
        print(f"Индекс '{INDEX_NAME}' создан")
    else:
        print(f"Индекс '{INDEX_NAME}' уже существует")

def save_search(query, ip_address):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO search_history (query, ip_address, timestamp) VALUES (?, ?, ?)',
        (query, ip_address, now)
    )
    conn.commit()
    conn.close()

def get_search_history(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT query, ip_address, timestamp 
        FROM search_history 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [{'query': row[0], 'ip': row[1], 'time': row[2]} for row in rows]

# Инициализация при импорте
init_db()
create_index()