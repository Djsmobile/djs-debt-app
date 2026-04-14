from flask import Flask, render_template, request, jsonify, session, redirect
import os
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

PASSWORD = os.environ.get("APP_PASSWORD", "DJs2025!")

DB_PATH = os.environ.get("DB_PATH", "debts.db")

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

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Incorrect password")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/")
    return render_template("index.html")

@app.route("/get_debts")
def get_debts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM debts").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/save_debts", methods=["POST"])
def save_debts():
    data = request.get_json()
    conn = get_conn()
    conn.execute("DELETE FROM debts")

    for d in data:
        conn.execute(
            "INSERT INTO debts (name, balance, rate, payment, due_day, paid, credit_limit) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d["name"], d["balance"], d["rate"], d["payment"], d["due_day"], d["paid"], d["credit_limit"])
        )

    conn.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    app.run()
