from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")
PASSWORD = "DJs2025!"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table_name, column_name, column_sql):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        conn.commit()


def init_db():
    conn = get_conn()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            payment REAL DEFAULT 0
        )
        '''
    )
    conn.commit()

    ensure_column(conn, "debts", "due_date", "TEXT")
    ensure_column(conn, "debts", "paid", "INTEGER DEFAULT 0")

    conn.close()


init_db()


@app.route("/", methods=["GET", "POST"])
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
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, balance, rate, payment, due_date, paid FROM debts ORDER BY id ASC"
    ).fetchall()
    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "name": row["name"] or "",
            "balance": float(row["balance"] or 0),
            "rate": float(row["rate"] or 0),
            "payment": float(row["payment"] or 0),
            "due_date": row["due_date"] or "",
            "paid": bool(row["paid"] or 0),
        }
        for row in rows
    ])


@app.route("/save_debts", methods=["POST"])
def save_debts():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or []

    conn = get_conn()
    conn.execute("DELETE FROM debts")

    for d in data:
        name = str(d.get("name", "")).strip()
        balance = float(d.get("balance", 0) or 0)
        rate = float(d.get("rate", 0) or 0)
        payment = float(d.get("payment", 0) or 0)
        due_date = str(d.get("due_date", "") or "").strip()
        paid = 1 if d.get("paid") else 0

        conn.execute(
            '''
            INSERT INTO debts (name, balance, rate, payment, due_date, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (name, balance, rate, payment, due_date, paid),
        )

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run()
