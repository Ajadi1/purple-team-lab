import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), "users.db")
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS users")
cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)")

users = [
    ("admin",  "S3cr3tAdminPass!", "admin"),
    ("ajadi",  "password123",      "user"),
    ("jsmith", "letmein",          "user"),
]
cur.executemany("INSERT INTO users (username, password, role) VALUES (?,?,?)", users)
conn.commit()
conn.close()
print(f"Database initialized with {len(users)} users")