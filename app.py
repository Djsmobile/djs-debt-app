from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3, os

app = Flask(__name__)
app.secret_key = "secret"

DB = "debts.db"

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn()
    c.execute('''CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY,
        name TEXT,
        balance REAL,
        rate REAL,
        payment REAL,
        due_day INTEGER,
        paid INTEGER,
        credit_limit REAL
    )''')
    c.commit()

init()

@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        session["ok"]=True
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dash():
    if not session.get("ok"): return redirect("/")
    return render_template("index.html")

@app.route("/get")
def get():
    c=conn()
    d=[dict(r) for r in c.execute("SELECT * FROM debts")]
    return jsonify(d)

@app.route("/save", methods=["POST"])
def save():
    data=request.json
    c=conn()
    c.execute("DELETE FROM debts")
    for d in data:
        c.execute("INSERT INTO debts (name,balance,rate,payment,due_day,paid,credit_limit) VALUES (?,?,?,?,?,?,?)",
        (d["name"],d["balance"],d["rate"],d["payment"],d["due_day"],d["paid"],d["credit_limit"]))
    c.commit()
    return {"ok":True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
