from flask import Flask, render_template, request, jsonify, session, redirect
import os
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

PASSWORD = os.environ.get("APP_PASSWORD", "DJs2025!")
DEFAULT_DB_CANDIDATES = [
    os.environ.get("DB_PATH"),
    "/data/debts.db",
    os.path.join(os.path.dirname(__file__), "debts.db"),
]


def resolve_db_path() -> str:
    """Pick the first writable database path."""
    errors = []

    for candidate in DEFAULT_DB_CANDIDATES:
        if not candidate:
            continue
        try:
            path = Path(candidate)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8"):
                pass
            return str(path)
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    raise RuntimeError("No writable database path found. " + " | ".join(errors))


DB_PATH = resolve_db_path()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            balance REAL NOT NULL DEFAULT 0,
            rate REAL NOT NULL DEFAULT 0,
            payment REAL NOT NULL DEFAULT 0,
            due_day INTEGER,
            paid INTEGER NOT NULL DEFAULT 0,
            credit_limit REAL NOT NULL DEFAULT 0
        )
        '''
    )
    conn.commit()
    conn.close()


init_db()


def to_float(value, default=0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def to_due_day(value):
    try:
        if value in (None, ""):
            return None
        day = int(value)
        if 1 <= day <= 31:
            return day
    except (TypeError, ValueError):
        pass
    return None


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


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


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "db_path": DB_PATH})


@app.route("/get_debts")
def get_debts():
    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 401

    conn = get_conn()
    rows = conn.execute("SELECT * FROM debts ORDER BY paid ASC, due_day ASC, id ASC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/save_debts", methods=["POST"])
def save_debts():
    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"status": "error", "message": "Invalid payload"}), 400

    conn = None
    try:
        conn = get_conn()
        conn.execute("BEGIN")
        conn.execute("DELETE FROM debts")

        for raw in data:
            if not isinstance(raw, dict):
                continue

            debt = {
                "name": str(raw.get("name", "")).strip(),
                "balance": max(0.0, to_float(raw.get("balance"), 0.0)),
                "rate": max(0.0, to_float(raw.get("rate"), 0.0)),
                "payment": max(0.0, to_float(raw.get("payment"), 0.0)),
                "due_day": to_due_day(raw.get("due_day")),
                "paid": 1 if bool(raw.get("paid", False)) else 0,
                "credit_limit": max(0.0, to_float(raw.get("credit_limit"), 0.0)),
            }

            conn.execute(
                """
                INSERT INTO debts (name, balance, rate, payment, due_day, paid, credit_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    debt["name"],
                    debt["balance"],
                    debt["rate"],
                    debt["payment"],
                    debt["due_day"],
                    debt["paid"],
                    debt["credit_limit"],
                ),
            )

        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        return jsonify({"status": "error", "message": str(exc), "db_path": DB_PATH}), 500
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
