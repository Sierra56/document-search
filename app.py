from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
from datetime import datetime

from config import ADMIN_PASSWORD
from models import list_docs, delete_doc, init_db, create_index
from utils import index_doc

app = Flask(__name__)
app.secret_key = 'dev-secret'  # В prod — env var
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

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
def index():
    query = request.args.get('q', '')
    results = []
    highlights = []
    history = session.get('search_history', [])
    
    if query:
        from elasticsearch import Elasticsearch
        from config import ES_HOST, INDEX_NAME
        es = Elasticsearch([ES_HOST])
        res = es.search(index=INDEX_NAME, body={
            'query': {'match': {'content': query}},
            'highlight': {'fields': {'content': {}}},
            'size': 20
        })
        results = res['hits']['hits']
        highlights = [hit['_source'] for hit in results]
        history = [q for q in history if q != query][:9] + [query]
        session['search_history'] = history
    
    return render_template('index.html', query=query, results=results, highlights=highlights, history=history)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            login_user(AdminUser())
            return redirect(url_for('admin'))
        flash('Неверный пароль')
    return render_template('admin_login.html')

@app.route('/admin')
@login_required
def admin():
    docs = list_docs()
    return render_template('admin.html', docs=docs)

@app.route('/admin/delete/<filename>')
@login_required
def admin_delete(filename):
    delete_doc(filename)
    flash(f'Документ {filename} удалён')
    return redirect(url_for('admin'))

@app.route('/admin/reindex/<filename>')
@login_required
def admin_reindex(filename):
    index_doc(filename)
    flash(f'Переиндексация {filename} запущена')
    return redirect(url_for('admin'))

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    session.pop('logged_in', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)