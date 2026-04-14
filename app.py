from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "secret"

DB_PATH = os.environ.get("DB_PATH", "debts.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY,
        name TEXT,
        balance REAL,
        rate REAL,
        payment REAL,
        due_day INTEGER,
        paid INTEGER,
        credit_limit REAL
    )
    """)
    conn.commit()
    conn.close()

init_db()

PASSWORD = "1234"  # change later

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

@app.route("/get_debts")
def get_debts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM debts").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/save", methods=["POST"])
def save():
    data = request.json
    conn = get_db()
    conn.execute("DELETE FROM debts")

    for d in data:
        conn.execute("""
        INSERT INTO debts (name,balance,rate,payment,due_day,paid,credit_limit)
        VALUES (?,?,?,?,?,?,?)
        """, (
            d.get("name"),
            d.get("balance"),
            d.get("rate"),
            d.get("payment"),
            d.get("due_day"),
            d.get("paid"),
            d.get("credit_limit")
        ))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# DO NOT RUN ON RENDER
if __name__ == "__main__":
    app.run(debug=True)