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


def column_names(conn, table_name):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]


def init_db():
    conn = get_conn()

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            payment REAL DEFAULT 0,
            due_day INTEGER,
            paid INTEGER DEFAULT 0
        )
        '''
    )
    conn.commit()

    cols = column_names(conn, "debts")

    if "due_day" not in cols:
        conn.execute("ALTER TABLE debts ADD COLUMN due_day INTEGER")
        conn.commit()

    if "paid" not in cols:
        conn.execute("ALTER TABLE debts ADD COLUMN paid INTEGER DEFAULT 0")
        conn.commit()

    # Backward compatibility for older versions using due_date text
    cols = column_names(conn, "debts")
    if "due_date" in cols:
        rows = conn.execute("SELECT id, due_date, due_day FROM debts").fetchall()
        for row in rows:
            if row["due_day"] is None and row["due_date"]:
                try:
                    day = int(str(row["due_date"]).split("-")[-1])
                    if 1 <= day <= 31:
                        conn.execute("UPDATE debts SET due_day = ? WHERE id = ?", (day, row["id"]))
                except Exception:
                    pass
        conn.commit()

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
        "SELECT id, name, balance, rate, payment, due_day, paid FROM debts ORDER BY id ASC"
    ).fetchall()
    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "name": row["name"] or "",
            "balance": float(row["balance"] or 0),
            "rate": float(row["rate"] or 0),
            "payment": float(row["payment"] or 0),
            "due_day": int(row["due_day"]) if row["due_day"] is not None else None,
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

        due_day_raw = d.get("due_day")
        due_day = None
        if due_day_raw not in (None, "", "null"):
            try:
                day = int(due_day_raw)
                if 1 <= day <= 31:
                    due_day = day
            except Exception:
                due_day = None

        paid = 1 if d.get("paid") else 0

        conn.execute(
            '''
            INSERT INTO debts (name, balance, rate, payment, due_day, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (name, balance, rate, payment, due_day, paid),
        )

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run()
