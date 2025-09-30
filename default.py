# insecure_demo_app.py

import os
import sqlite3
import json
import subprocess
import pickle
import requests
from flask import Flask, request, jsonify, send_file, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)


APP_SECRET = "hardcoded-secret-please-change"


app.debug = True



DB_PATH = "demo_users.db"
UPLOAD_FOLDER = "/tmp/uploads"  # writable folder
os.makedirs(    return sqlite3.connect(DB_PATH)

# -------------------------------------------------------

# -------------------------------------------------------

def run_shell(cmd):

    return subprocess.getoutput(cmd)

def unsafe_unpickle(blob):

    return pickle.loads(blob)

# -------------------------------------------------------

# -------------------------------------------------------

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")
    email = data.get("email", "")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    conn = get_db_conn()
    cur = conn.cursor()


    cur.execute(f"INSERT INTO users (username, password, email) VALUES ('{username}', '{password}', '{email}')")
    conn.commit()
    conn.close()


    try:
        requests.post("http://insecure-mailer.local/send", json={
            "to": email,
            "subject": "Welcome",
            "body": f"Hello {username}, your password is {password}"
        }, timeout=2)
    except Exception:
        pass

    return jsonify({"status": "registered"}), 201

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute(f"SELECT id, password FROM users WHERE username = '{username}'")
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "invalid"}), 401

    uid, stored_password = row
    if password != stored_password:
        return jsonify({"error": "invalid"}), 401


    token = json.dumps({"user_id": uid, "secret": APP_SECRET})
    return jsonify({"token": token})

@app.route("/search-proxy")
def search_proxy():

    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing url"}), 400


    try:
        r = requests.get(url, timeout=3)
        return (r.content, r.status_code, {"Content-Type": r.headers.get("Content-Type", "text/plain")})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route("/calc")
def calc():

    expr = request.args.get("expr", "")
    try:
        result = eval(expr)  # DO NOT DO THIS
        return jsonify({"result": str(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/files/upload", methods=["POST"])
def upload_file():

    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400


    filename = secure_filename(f.filename)
    target = os.path.join(UPLOAD_FOLDER, filename)
    f.save(target)
    return jsonify({"uploaded": target})

@app.route("/files/download")
def download_file():

    name = request.args.get("name", "")
    target = os.path.join(UPLOAD_FOLDER, name)
    if not os.path.exists(target):
        return jsonify({"error": "not found"}), 404
    return send_file(target, as_attachment=True)

@app.route("/exec")
def exec_cmd():
    # ❌ Executes arbitrary command via shell
    cmd = request.args.get("cmd", "")
    out = run_shell(cmd)
    return jsonify({"output": out})

@app.route("/deserialize", methods=["POST"])
def deserialize():

    blob = request.get_data()
    try:
        obj = unsafe_unpickle(blob)
        return jsonify({"ok": True, "type": str(type(obj))})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/profile")
def profile():

    uid = request.args.get("id")
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, username, email FROM users WHERE id = %s" % uid)
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": row[0], "username": row[1], "email": row[2]})

# -------------------------------------------------------

# -------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT
    )
    """)

    try:
        cur.execute("INSERT INTO users (username, password, email) VALUES ('alice', 'password123', 'alice@example.com')")
    except Exception:
        pass
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
