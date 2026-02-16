from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_caching import Cache
from datetime import datetime
import json
import os

from config import ADMIN_PASSWORD, DOCS_PATH, INDEX_NAME, ES_HOST
from models import list_docs, delete_doc, init_db, create_index, save_search, get_search_history
from utils import index_doc

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'

# Настройка кэша с обработкой ошибок подключения
cache_config = {
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://redis:6379/0'),
    'CACHE_DEFAULT_TIMEOUT': 600
}

cache = Cache(app, config=cache_config)

# Если Redis недоступен — отключаем кэш, чтобы приложение не падало
try:
    cache.cache._client.ping()  # тест подключения
    print("Redis подключён успешно")
except Exception as e:
    print(f"Redis недоступен: {e}. Кэширование отключено.")
    cache.config['CACHE_TYPE'] = 'null'  # отключаем кэш полностью

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = None

class AdminUser(UserMixin):
    def get_id(self):
        return 'admin'

@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin' and session.get('logged_in'):
        return AdminUser()
    return None

init_db()
create_index()

@app.route('/')
@cache.cached(timeout=600, query_string=True)
def index():
    query = request.args.get('q', '')
    highlights = []
    history = session.get('search_history', [])
    
    if query:
        from elasticsearch import Elasticsearch
        es = Elasticsearch([ES_HOST])
        
        try:
            res = es.search(index=INDEX_NAME, body={
                'query': {'match': {'content': query}},
                'highlight': {
                    'fields': {
                        'content': {
                            'pre_tags': ['<mark>'],
                            'post_tags': ['</mark>'],
                            'fragment_size': 180,
                            'number_of_fragments': 5,
                            'order': 'score'
                        }
                    }
                },
                'size': 15,
                '_source': ['filename', 'added_date', 'content']
            })
            
            hits = res.get('hits', {}).get('hits', [])
            for hit in hits:
                source = hit.get('_source', {})
                highlight = hit.get('highlight', {})
                
                if 'content' in highlight:
                    highlighted_short = ' … '.join(highlight['content'][:2])
                    highlighted_full = ' … '.join(highlight['content'])
                else:
                    content = source.get('content', '')
                    highlighted_short = highlighted_full = (content[:400] + '…') if content else '(текст отсутствует)'
                
                item = source.copy()
                item['highlighted_short'] = highlighted_short
                item['highlighted_full'] = highlighted_full
                highlights.append(item)
            
            ip = request.remote_addr
            save_search(query, ip)
            
            history = [q for q in history if q != query][:9] + [query]
            session['search_history'] = history
        
        except Exception as e:
            flash(f'Ошибка поиска: {str(e)}', 'error')
    
    current_year = datetime.now().year
    
    return render_template('index.html', query=query, highlights=highlights, history=history, current_year=current_year)

@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/history')
def history():
    history_records = get_search_history(20)
    return render_template('history.html', history=history_records)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            login_user(AdminUser())
            return redirect(url_for('admin'))
        flash('Неверный пароль', 'error')
    return render_template('admin_login.html')

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/admin/delete/<filename>')
@login_required
def admin_delete(filename):
    delete_doc(filename)
    flash(f'Удалён: {filename}', 'success')
    cache.clear()
    return redirect(url_for('admin'))

@app.route('/admin/delete_all')
@login_required
def admin_delete_all():
    docs_list = list_docs()
    count = len(docs_list)
    for doc in docs_list:
        delete_doc(doc['filename'])
    flash(f'Удалено {count} документов', 'success')
    cache.clear()
    return redirect(url_for('admin'))

@app.route('/admin/clear_cache')
@login_required
def admin_clear_cache():
    cache.clear()
    flash('Кэш полностью очищен', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/reindex/<filename>')
@login_required
def admin_reindex(filename):
    index_doc(filename)
    flash(f'Переиндексация запущена: {filename}', 'info')
    cache.clear()
    return redirect(url_for('admin'))

@app.route('/admin/reindex_all')
@login_required
def admin_reindex_all():
    from config import DOCS_PATH
    count = 0
    for f in os.listdir(DOCS_PATH):
        if f.lower().endswith(('.pdf', '.docx', '.rtf')):
            index_doc(f)
            count += 1
    flash(f'Переиндексация запущена для {count} файлов', 'info')
    cache.clear()
    return redirect(url_for('admin'))

@app.route('/api/docs')
def api_docs():
    return jsonify(list_docs())

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    session.pop('logged_in', None)
    flash('Вы вышли из админ-панели', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)