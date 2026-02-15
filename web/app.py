from flask import Flask, render_template, request, redirect, session, jsonify, send_file, Response, flash
from elasticsearch import Elasticsearch
from flask_caching import Cache
import redis, os, json, csv
from io import StringIO
from datetime import datetime
import bcrypt

app = Flask(__name__)
app.secret_key = "change_me"

es = Elasticsearch(os.getenv("ES_HOST"))
redis_client = redis.Redis(host=os.getenv("REDIS_HOST"), decode_responses=True)

cache = Cache(app, config={
    "CACHE_TYPE": "redis",
    "CACHE_REDIS_HOST": os.getenv("REDIS_HOST"),
    "CACHE_REDIS_DB": 1
})

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"

# ----------------- helpers -----------------

def audit(action, details=""):
    redis_client.lpush("audit:log", json.dumps({
        "user": session.get("user", "admin"),
        "action": action,
        "details": details,
        "time": datetime.utcnow().isoformat()
    }))

def admin_required():
    if not session.get("admin"):
        return redirect("/admin/login")

# ----------------- auth -----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            audit("ADMIN_LOGIN")
            return redirect("/admin")
    return render_template("admin.html", login=True)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/")

# ----------------- search -----------------

@app.route("/")
def search():
    q = request.args.get("q", "").strip()
    results = []

    if q:
        redis_client.zincrby("search:count", 1, q)

        res = es.search(index="documents", body={
            "query": {"match": {"content": q}},
            "highlight": {"fields": {"content": {}}}
        })

        for hit in res["hits"]["hits"]:
            results.append({
                "filename": hit["_source"]["filename"],
                "snippet": hit.get("highlight", {}).get("content", [""])[0]
            })

    return render_template("search.html", q=q, results=results)

# ----------------- admin -----------------

@app.route("/admin")
def admin():
    admin_required()
    res = es.search(index="documents", body={"query": {"match_all": {}}}, size=1000)
    docs = res["hits"]["hits"]
    return render_template("admin.html", docs=docs)

@app.route("/admin/redis/flush", methods=["POST"])
def redis_flush():
    admin_required()
    redis_client.flushdb()
    audit("REDIS_FLUSH")
    return redirect("/admin")

# ----------------- audit page -----------------

@app.route("/admin/audit")
def admin_audit():
    admin_required()
    logs = [json.loads(x) for x in redis_client.lrange("audit:log", 0, 100)]
    return render_template("audit.html", logs=logs)

# ----------------- reports -----------------

@app.route("/admin/reports")
def reports():
    admin_required()
    top = redis_client.zrevrange("search:count", 0, 10, withscores=True)
    return render_template("reports.html", top=top)

@app.route("/admin/reports/export/csv")
def export_csv():
    admin_required()
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Запрос", "Количество"])
    for q, c in redis_client.zrevrange("search:count", 0, -1, withscores=True):
        writer.writerow([q, int(c)])
    audit("EXPORT_CSV")
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=report.csv"})

# -----------------

app.run(host="0.0.0.0", port=8080)