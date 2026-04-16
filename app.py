from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")
PASSWORD = os.environ.get("APP_PASSWORD", "1234")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_column(conn, table_name, column_name, column_sql):
    cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        conn.commit()

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            payment REAL DEFAULT 0,
            due_day INTEGER,
            paid INTEGER DEFAULT 0,
            credit_limit REAL DEFAULT 0,
            paid_this_month INTEGER DEFAULT 0,
            paycheck_group TEXT DEFAULT 'check1'
        )
    """)
    conn.commit()
    ensure_column(conn, "debts", "due_day", "INTEGER")
    ensure_column(conn, "debts", "paid", "INTEGER DEFAULT 0")
    ensure_column(conn, "debts", "credit_limit", "REAL DEFAULT 0")
    ensure_column(conn, "debts", "paid_this_month", "INTEGER DEFAULT 0")
    ensure_column(conn, "debts", "paycheck_group", "TEXT DEFAULT 'check1'")
    conn.close()

init_db()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST" and request.form.get("password") == PASSWORD:
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
        return jsonify({"error":"Unauthorized"}), 401
    conn = get_db()
    rows = conn.execute("SELECT * FROM debts ORDER BY id ASC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/save", methods=["POST"])
@app.route("/save_debts", methods=["POST"])
def save_debts():
    if not session.get("logged_in"):
        return jsonify({"error":"Unauthorized"}), 401
    data = request.json or []
    conn = get_db()
    conn.execute("DELETE FROM debts")
    for d in data:
        due_day = d.get("due_day")
        if due_day in ("", None, "null"):
            due_day = None
        else:
            try:
                due_day = int(due_day)
                if due_day < 1 or due_day > 31:
                    due_day = None
            except Exception:
                due_day = None
        paycheck_group = str(d.get("paycheck_group", "check1") or "check1").lower()
        if paycheck_group not in ("check1", "check2"):
            paycheck_group = "check1"
        conn.execute("""
            INSERT INTO debts (name, balance, rate, payment, due_day, paid, credit_limit, paid_this_month, paycheck_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(d.get("name","")).strip(),
            float(d.get("balance",0) or 0),
            float(d.get("rate",0) or 0),
            float(d.get("payment",0) or 0),
            due_day,
            1 if d.get("paid") else 0,
            float(d.get("credit_limit",0) or 0),
            1 if d.get("paid_this_month") else 0,
            paycheck_group
        ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
