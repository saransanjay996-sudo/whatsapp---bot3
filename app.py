from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import os
import psycopg2

app = Flask(__name__)

# 🛍️ Products
products = {
    "black shirt": {
        "price": "₹999",
        "sizes": ["M", "L", "XL"],
        "delivery": "3-5 days"
    },
    "white tshirt": {
        "price": "₹799",
        "sizes": ["S", "M", "L"],
        "delivery": "2-4 days"
    }
}

# 👤 User state
user_state = {}

# 🔗 DB connection (safe)
def get_db_connection():
    try:
        return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
    except Exception as e:
        print("❌ DB CONNECT ERROR:", e)
        return None

# 🧱 Init DB (safe)
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

# 💾 Save
def save_to_db(data):
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ DB NOT CONNECTED")
            return

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO orders (name, phone, product, size, address, date, time, delivery)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, data)

        conn.commit()
        cur.close()
        conn.close()

        print("✅ SAVED:", data)

    except Exception as e:
        print("❌ SAVE ERROR:", e)

# 🔧 init route
@app.route("/initdb")
def force_init():
    init_db()
    return "DB Initialized"

# 📦 orders view
@app.route("/orders")
def view_orders():
    try:
        conn = get_db_connection()
        if not conn:
            return "DB connection failed"

        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return "No orders yet"

        result = ""
        for r in rows:
            result += f"""
ID: {r[0]}
Name: {r[1]}
Phone: {r[2]}
Product: {r[3]}
Size: {r[4]}
Address: {r[5]}
Date: {r[6]}
Time: {r[7]}
Delivery: {r[8]}
----------------------
"""
        return result

    except Exception as e:
        return str(e)

# 🏠 home
@app.route("/")
def home():
    return "Bot is running"

@app.route("/webhook", methods=['POST'])
def webhook():
    print("🚀 WEBHOOK STARTED")

    incoming_msg = request.values.get('Body')
    user_number = request.values.get('From')

    print("📩 RAW:", incoming_msg)

    if not incoming_msg or not user_number:
        return "OK"

    incoming_msg = incoming_msg.strip().lower()
    phone = user_number.replace("whatsapp:", "")

    resp = MessagingResponse()
    msg = resp.message()

    # 💥 DIRECT ORDER FORMAT (MOST IMPORTANT)
    # Example: Sanjay, Chennai
    if "," in incoming_msg:
        print("🔥 DIRECT ORDER DETECTED")

        parts = incoming_msg.split(",", 1)
        name = parts[0].strip()
        address = parts[1].strip()

        # fallback defaults (to avoid failure)
        product = "black shirt"
        size = "M"

        now = datetime.now()

        save_to_db([
            name,
            phone,
            product,
            size,
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            "3-5 days"
        ])

        print("✅ SAVED DIRECT ORDER")

        msg.body(
            f"""Order Confirmed ✅

Product: {product}
Size: {size}
Delivery: 3-5 days"""
        )

        return str(resp)

    # 💥 SIMPLE FLOW (OPTIONAL)
    if "black shirt" in incoming_msg:
        msg.body("Black shirt available. Sizes: M, L, XL\nSend size")
        return str(resp)

    if incoming_msg.upper() in ["S", "M", "L", "XL"]:
        msg.body("Send name and address")
        return str(resp)

    msg.body("Send 'black shirt' or 'white tshirt' ")
    return str(resp)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
