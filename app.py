import os
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
app.config["DEBUG"] = True
SECRET_KEY = "12345"

@app.route("/users", methods=["POST"])
def add_user():
    data = request.json
    username = data.get("username")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO users (username) VALUES ('{username}')")
    conn.commit()
    conn.close()

    return jsonify({"message": "User added!"})

@app.route("/health")
def health():
    return "clear"
