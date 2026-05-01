from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import os
import psycopg2

app = Flask(__name__)

products = {
    "black shirt": {"price": "₹999", "sizes": ["M", "L", "XL"], "delivery": "3-5 days"},
    "white tshirt": {"price": "₹799", "sizes": ["S", "M", "L"], "delivery": "2-4 days"}
}

user_state = {}

# 🔗 SAFE DB CONNECT
def get_db_connection():
    try:
        return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
    except Exception as e:
        print("❌ DB CONNECT ERROR:", e)
        return None

# 🧱 SAFE INIT
def init_db():
    try:
        conn = get_db_connection()
        if not conn:
            return

        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            product TEXT,
            size TEXT,
            address TEXT,
            date TEXT,
            time TEXT,
            delivery TEXT
        )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ TABLE READY")

    except Exception as e:
        print("❌ INIT ERROR:", e)

# 💾 SAFE SAVE
def save_to_db(data):
    try:
        print("🔥 SAVING:", data)

        conn = get_db_connection()
        if not conn:
            print("❌ NO DB CONNECTION")
            return

        cur = conn.cursor()
        cur.execute("""
        INSERT INTO orders (name, phone, product, size, address, date, time, delivery)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, data)

        conn.commit()
        cur.close()
        conn.close()

        print("✅ SAVED")

    except Exception as e:
        print("❌ SAVE ERROR:", e)

@app.route("/")
def home():
    return "Bot running"

@app.route("/initdb")
def force_init():
    init_db()
    return "DB Initialized"

@app.route("/orders")
def view_orders():
    try:
        conn = get_db_connection()
        if not conn:
            return "DB not connected"

        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return "No orders yet"

        return str(rows)

    except Exception as e:
        return str(e)

@app.route("/webhook", methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    phone = request.values.get('From').replace("whatsapp:", "")

    resp = MessagingResponse()
    msg = resp.message()

    if phone not in user_state:
        user_state[phone] = {"step": None, "product": None, "size": None}

    state = user_state[phone]

    # CANCEL
    if incoming_msg in ["cancel", "stop"]:
        user_state[phone] = {"step": None, "product": None, "size": None}
        msg.body("Cancelled")
        return str(resp)

    # PRODUCT
    if state["step"] is None:
        for p in products:
            if p in incoming_msg:
                state["product"] = p
                state["step"] = "size"
                msg.body(f"Choose size: {', '.join(products[p]['sizes'])}")
                return str(resp)

    # SIZE
    if state["step"] == "size":
        if incoming_msg.upper() in products[state["product"]]["sizes"]:
            state["size"] = incoming_msg.upper()
            state["step"] = "address"
            msg.body("Send name and address")
        else:
            msg.body("Invalid size")
        return str(resp)

    # ADDRESS
    if state["step"] == "address":
        parts = incoming_msg.split(",", 1)
        name = parts[0]
        address = parts[1] if len(parts) > 1 else ""

        now = datetime.now()

        save_to_db([
            name,
            phone,
            state["product"],
            state["size"],
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            products[state["product"]]["delivery"]
        ])

        msg.body("Order Confirmed ✅")
        user_state[phone] = {"step": None, "product": None, "size": None}
        return str(resp)

    msg.body("Send product name")
    return str(resp)


if __name__ == "__main__":
    init_db()  # safe now
    app.run(host="0.0.0.0", port=5000)
