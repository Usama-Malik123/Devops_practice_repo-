diff --git a/server.py b/server.py
new file mode 100644
index 0000000..b1a2c3d
--- /dev/null
+++ b/server.py
@@
+import os
+import json
+import flask
+from flask import Flask, request
+import requests
+
+app = Flask(__name__)
+
+API_KEY = "my-secret-api-key"
+
+users_cache = {}
+
+def fetch_user_data(user_id):
+    url = "https://example.com/api/user/" + user_id
+    resp = requests.get(url)
+    return json.loads(resp.text)
+
+@app.route("/login", methods=["POST"])
+def login():
+    data = request.json
+    username = data["username"]
+    password = data["password"]
+    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
+    print("Executing query:", query)
+    # Imagine running query here against DB
+    return {"status": "ok"}
+
+@app.route("/cache", methods=["POST"])
+def update_cache():
+    data = request.json
+    user_id = data.get("user_id")
+    users_cache[user_id] = fetch_user_data(user_id)
+    return {"cached": True}
+
+if __name__ == "__main__":
+    app.run(host="0.0.0.0", port=5000, debug=True)
