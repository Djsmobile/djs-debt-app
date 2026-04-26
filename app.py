from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3
import os
import json
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.permanent_session_lifetime = timedelta(days=30)
DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")
PASSWORD = os.environ.get("APP_PASSWORD", "1234")

DEFAULT_SETTINGS = {"check1_income": 0, "check2_income": 0, "safety_buffer": 300}

CREDIT_REPORT_SNAPSHOT = {
    "report_date": "2026-04-24", "score": 548, "rating": "Unfavorable",
    "total_accounts": 14, "open_accounts": 13, "closed_accounts": 1,
    "total_balances": 22936, "monthly_payments": 1227,
    "delinquent": 0, "derogatory": 0, "credit_inquiries": 1, "public_records": 1,
}

CREDIT_REPORT_ACCOUNTS = [
    {"name":"GOLDEN 1 CU - 29755****","balance":2429,"credit_limit":0,"payment":108,"account_type":"Unsecured loan","paycheck_group":"check1"},
    {"name":"LENDING CLUB - 6582****","balance":0,"credit_limit":0,"payment":234,"account_type":"Unsecured loan","paycheck_group":"check2","paid":True},
    {"name":"SCHOOLS FIN - 310867******","balance":0,"credit_limit":0,"payment":0,"account_type":"Auto loan","paycheck_group":"check2","paid":True},
    {"name":"THD/CBNA - 603532**********","balance":332,"credit_limit":500,"payment":0,"account_type":"Charge account","paycheck_group":"check1"},
    {"name":"SYNCB/HFT - 604420**********","balance":746,"credit_limit":1500,"payment":0,"account_type":"Charge account","paycheck_group":"check1"},
    {"name":"CCB/CHLDPLCE - 578097**********","balance":54,"credit_limit":750,"payment":0,"account_type":"Charge account","paycheck_group":"check1"},
    {"name":"LES SCHWAB - 6292****","balance":195,"credit_limit":500,"payment":0,"account_type":"Charge account","paycheck_group":"check1"},
    {"name":"CAPITAL ONE - 517805****** $500 limit","balance":400,"credit_limit":500,"payment":0,"account_type":"Credit card","paycheck_group":"check1"},
    {"name":"WFBNA CARD - 414718******","balance":5889,"credit_limit":6000,"payment":0,"account_type":"Credit card","paycheck_group":"check2"},
    {"name":"GS BANK USA - 11**","balance":445,"credit_limit":450,"payment":0,"account_type":"Credit card","paycheck_group":"check1"},
    {"name":"CAPITAL ONE - 517805****** $4,800 limit","balance":4810,"credit_limit":4800,"payment":0,"account_type":"Credit card","paycheck_group":"check2"},
    {"name":"TBOM RETAIL - 763700**********","balance":2449,"credit_limit":6400,"payment":0,"account_type":"Credit card","paycheck_group":"check2"},
    {"name":"CAPITAL ONE - 515676******","balance":1928,"credit_limit":2000,"payment":0,"account_type":"Credit card","paycheck_group":"check2"},
    {"name":"CAPITAL ONE - 414709******","balance":3259,"credit_limit":3100,"payment":0,"account_type":"Flexible spending credit card","paycheck_group":"check2"},
    {"name":"AFFIRM INC - JJZZ****","balance":238,"credit_limit":0,"payment":0,"account_type":"Buy Now Pay Later","paycheck_group":"check1"},
    {"name":"AFFIRM INC - 2WEK4**","balance":399,"credit_limit":0,"payment":0,"account_type":"Buy Now Pay Later","paycheck_group":"check1"},
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table_name, column_name, column_sql):
    cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        conn.commit()


def normalize_history(raw_history):
    if isinstance(raw_history, str):
        try:
            raw_history = json.loads(raw_history)
        except Exception:
            raw_history = []
    if not isinstance(raw_history, list):
        return []
    cleaned = []
    for item in raw_history[:10]:
        if not isinstance(item, dict):
            continue
        amount = max(0.0, float(item.get("amount", 0) or 0))
        if amount <= 0:
            continue
        cleaned.append({"amount": round(amount, 2), "type": str(item.get("type", "custom") or "custom")[:20], "label": str(item.get("label", "Payment") or "Payment")[:40]})
    return cleaned


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
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
            paycheck_group TEXT DEFAULT 'check1',
            monthly_paid_amount REAL DEFAULT 0,
            last_payment_amount REAL DEFAULT 0,
            payment_history TEXT DEFAULT '[]',
            account_type TEXT DEFAULT '',
            report_source TEXT DEFAULT '',
            report_date TEXT DEFAULT '',
            is_recurring INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    for name, sql in [
        ("due_day", "INTEGER"), ("paid", "INTEGER DEFAULT 0"), ("credit_limit", "REAL DEFAULT 0"),
        ("paid_this_month", "INTEGER DEFAULT 0"), ("paycheck_group", "TEXT DEFAULT 'check1'"),
        ("monthly_paid_amount", "REAL DEFAULT 0"), ("last_payment_amount", "REAL DEFAULT 0"),
        ("payment_history", "TEXT DEFAULT '[]'"), ("account_type", "TEXT DEFAULT ''"),
        ("report_source", "TEXT DEFAULT ''"), ("report_date", "TEXT DEFAULT ''"),
        ("is_recurring", "INTEGER DEFAULT 0"),
    ]:
        ensure_column(conn, "debts", name, sql)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


init_db()


def fetch_all_debts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM debts ORDER BY id ASC").fetchall()
    conn.close()
    cleaned = []
    for r in rows:
        item = dict(r)
        item["paid"] = 1 if item.get("paid") else 0
        item["paid_this_month"] = 1 if item.get("paid_this_month") else 0
        item["paycheck_group"] = "check2" if item.get("paycheck_group") == "check2" else "check1"
        item["monthly_paid_amount"] = float(item.get("monthly_paid_amount") or 0)
        item["last_payment_amount"] = float(item.get("last_payment_amount") or 0)
        item["payment_history"] = normalize_history(item.get("payment_history"))
        item["account_type"] = str(item.get("account_type") or "")
        item["report_source"] = str(item.get("report_source") or "")
        item["report_date"] = str(item.get("report_date") or "")
        item["is_recurring"] = 1 if item.get("is_recurring") else 0
        if item["is_recurring"]:
            item["balance"] = 0
            item["credit_limit"] = 0
            item["rate"] = 0
            if not item["account_type"]:
                item["account_type"] = "Monthly Bill"
        cleaned.append(item)
    return cleaned


def fetch_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings = dict(DEFAULT_SETTINGS)
    for row in rows:
        if row["key"] in settings:
            try:
                settings[row["key"]] = float(row["value"] or 0)
            except Exception:
                pass
    return settings

def save_settings_payload(payload):
    cleaned = {}
    for key, default in DEFAULT_SETTINGS.items():
        try:
            cleaned[key] = max(0.0, float(payload.get(key, default) or 0))
        except Exception:
            cleaned[key] = float(default)
    conn = get_db()
    for key, value in cleaned.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
    return cleaned


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Wrong password")
    if session.get("logged_in"):
        return redirect("/dashboard")
    return render_template("login.html", error=None)


@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/")
    return render_template("index.html", initial_debts=json.dumps(fetch_all_debts()), initial_settings=json.dumps(fetch_settings()), credit_report_snapshot=json.dumps(CREDIT_REPORT_SNAPSHOT), credit_report_accounts=json.dumps(CREDIT_REPORT_ACCOUNTS))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/get_debts")
def get_debts_route():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(fetch_all_debts())


@app.route("/credit_report_import")
def credit_report_import():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"snapshot": CREDIT_REPORT_SNAPSHOT, "accounts": CREDIT_REPORT_ACCOUNTS})


@app.route("/settings", methods=["GET", "POST"])
def settings_route():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return jsonify(fetch_settings())
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload"}), 400
    return jsonify({"ok": True, "settings": save_settings_payload(data)})


@app.route("/save", methods=["POST"])
@app.route("/save_debts", methods=["POST"])
def save_debts():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Invalid payload"}), 400
    conn = get_db()
    conn.execute("DELETE FROM debts")
    for d in data:
        if not isinstance(d, dict):
            continue
        try:
            due_day = d.get("due_day")
            due_day = None if due_day in ("", None, "null") else int(due_day)
            if due_day is not None and (due_day < 1 or due_day > 31):
                due_day = None
        except Exception:
            due_day = None
        paycheck_group = str(d.get("paycheck_group", "check1") or "check1").lower()
        if paycheck_group not in ("check1", "check2"):
            paycheck_group = "check1"
        name = str(d.get("name", "")).strip()
        is_recurring = 1 if d.get("is_recurring") else 0
        balance = max(0.0, float(d.get("balance", 0) or 0))
        rate = float(d.get("rate", 0) or 0)
        payment = max(0.0, float(d.get("payment", 0) or 0))
        paid = 1 if d.get("paid") else 0
        credit_limit = max(0.0, float(d.get("credit_limit", 0) or 0))
        if is_recurring:
            balance = 0
            rate = 0
            credit_limit = 0
            paid = 0
        monthly_paid_amount = max(0.0, float(d.get("monthly_paid_amount", 0) or 0))
        last_payment_amount = max(0.0, float(d.get("last_payment_amount", 0) or 0))
        paid_this_month = 1 if d.get("paid_this_month") or monthly_paid_amount > 0 else 0
        payment_history = json.dumps(normalize_history(d.get("payment_history")))
        account_type = str(d.get("account_type", "") or "")[:80]
        report_source = str(d.get("report_source", "") or "")[:80]
        report_date = str(d.get("report_date", "") or "")[:20]
        conn.execute("""
            INSERT INTO debts (
                name, balance, rate, payment, due_day, paid, credit_limit,
                paid_this_month, paycheck_group, monthly_paid_amount, last_payment_amount,
                payment_history, account_type, report_source, report_date, is_recurring
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, balance, rate, payment, due_day, paid, credit_limit, paid_this_month,
              paycheck_group, monthly_paid_amount, last_payment_amount, payment_history,
              account_type, report_source, report_date, is_recurring))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
