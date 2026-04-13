
from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3, os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")
PASSWORD = "DJs2025!"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL,
            rate REAL,
            payment REAL,
            due_day INTEGER,
            paid INTEGER,
            credit_limit REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/")
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/get_debts")
def get_debts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM debts").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/save_debts", methods=["POST"])
def save_debts():
    data = request.json
    conn = get_conn()
    conn.execute("DELETE FROM debts")
    for d in data:
        conn.execute(
            "INSERT INTO debts (name,balance,rate,payment,due_day,paid,credit_limit) VALUES (?,?,?,?,?,?,?)",
            (d["name"], d["balance"], d["rate"], d["payment"], d["due_day"], int(d["paid"]), d["credit_limit"])
        )
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run()
