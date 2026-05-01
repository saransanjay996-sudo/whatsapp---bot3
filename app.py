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

# 🤖 webhook
@app.route("/webhook", methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    user_number = request.values.get('From')
    phone = user_number.replace("whatsapp:", "")

    resp = MessagingResponse()
    msg = resp.message()

    if phone not in user_state:
        user_state[phone] = {"step": None, "product": None, "size": None}

    state = user_state[phone]

    print("STATE:", state, "MSG:", incoming_msg)

    # ❌ CANCEL
    if incoming_msg in ["cancel", "stop", "exit"]:
        user_state[phone] = {"step": None, "product": None, "size": None}
        msg.body("Order cancelled ❌")
        return str(resp)

    # 🔍 detect product
    found_product = None
    for p in products:
        if p in incoming_msg:
            found_product = p
            break

    # 💡 Q&A MODE
    if state["step"] is None and found_product:
        p = products[found_product]

        if "price" in incoming_msg:
            msg.body(f"{found_product.title()} price is {p['price']}")
            return str(resp)

        elif "size" in incoming_msg:
            msg.body(f"Sizes: {', '.join(p['sizes'])}")
            return str(resp)

        elif "delivery" in incoming_msg:
            msg.body(f"Delivery: {p['delivery']}")
            return str(resp)

        else:
            state["product"] = found_product
            state["step"] = "ask_size"
            msg.body(f"{found_product.title()} available. Sizes: {', '.join(p['sizes'])}")
            return str(resp)

    # 📏 SIZE
    if state["step"] == "ask_size":
        size = incoming_msg.upper()

        if size in products[state["product"]]["sizes"]:
            state["size"] = size
            state["step"] = "ask_address"
            msg.body("Send name and address (Name, Address)")
        else:
            msg.body("Invalid size")
        return str(resp)

    # 📦 ADDRESS → SAVE
    if state["step"] == "ask_address":
        parts = incoming_msg.split(",", 1)
        name = parts[0].strip()
        address = parts[1].strip() if len(parts) > 1 else ""

        now = datetime.now()

        data = [
            name,
            phone,
            state["product"],
            state["size"],
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            products[state["product"]]["delivery"]
        ]

        save_to_db(data)

        msg.body(
            f"""Order Confirmed ✅

Product: {state['product'].title()}
Size: {state['size']}
Delivery: {products[state['product']]['delivery']}"""
        )

        user_state[phone] = {"step": None, "product": None, "size": None}
        return str(resp)

    msg.body("Send product like 'black shirt'")
    return str(resp)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
