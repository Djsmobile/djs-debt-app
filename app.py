from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3, os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS debts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, balance REAL, rate REAL, payment REAL)")
    conn.commit()
    conn.close()

init_db()

PASSWORD = "DJs2025!"

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM debts")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/save_debts", methods=["POST"])
def save_debts():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM debts")
    for d in data:
        c.execute("INSERT INTO debts (name,balance,rate,payment) VALUES (?,?,?,?)",(d["name"], d["balance"], d["rate"], d["payment"]))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run()
