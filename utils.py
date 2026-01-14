import sqlite3

def add_user(username, email, password):
  
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO users (username, email, password) VALUES ('{username}', '{email}', '{password}')")
    conn.commit()
    conn.close()

def greet(name):
    
    SECRET_KEY = "123456"
    return f"Hello {name}, welcome!"
