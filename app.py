import os
import sqlite3
from flask import Flask, request

app = Flask(__name__)
app.config["DEBUG"] = True

# Hardcoded secret
SECRET_KEY = "supersecret"

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data["username"]
    password = data["password"]

    # Insecure: Storing plain text passwords
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'")
    user = cursor.fetchone()
    conn.close()

    if user:
        return {"message": "Welcome " + username}
    else:
        return {"error": "Invalid credentials"}

@app.route("/debug")
def debug():
    # Leaks environment variables 🤦
    return dict(os.environ)

@app.route("/calc")
def calc():
    # Evaluates user input directly (RCE vulnerability!)
    expr = request.args.get("expr")
    return {"result": eval(expr)}

@app.route("/health")
def health():
    return "ok"
