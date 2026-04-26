from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import os
import psycopg2

app = Flask(__name__)

# 🛍️ Product Database
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

# 👤 User State
user_state = {}

# 🗄️ DB CONNECTION
def get_db_connection():
    print("🔗 Connecting to DB...")
    return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')

# 🧱 INIT TABLE
def init_db():
    try:
        conn = get_db_connection()
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
        import traceback
        print("❌ INIT ERROR:")
        print(traceback.format_exc())

# 💾 SAVE DATA
def save_to_db(data):
    try:
        print("🔥 BEFORE SAVE")
        conn = get_db_connection()
        print("✅ CONNECTED")

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
        import traceback
        print("❌ SAVE ERROR:")
        print(traceback.format_exc())

# 🔧 FORCE INIT ROUTE
@app.route("/initdb")
def force_init():
    init_db()
    return "DB Initialized ✅"

# 🏠 HOME
@app.route("/")
def home():
    return "Bot is running"

# 📦 VIEW ORDERS
@app.route("/orders")
def view_orders():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        result = ""
        for row in rows:
            result += f"{row}\n\n"

        return result if result else "No orders yet"

    except Exception as e:
        import traceback
        return traceback.format_exc()

# 🤖 WHATSAPP BOT
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

    # 🔍 Detect product
    found_product = None
    for product in products:
        if product in incoming_msg:
            found_product = product
            break

    # 💡 Q&A
    if state["step"] is None and found_product:
        p = products[found_product]

        if "price" in incoming_msg:
            msg.body(f"{found_product} price is {p['price']}")
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
            msg.body(f"Available sizes: {', '.join(p['sizes'])}")
            return str(resp)

    # SIZE
    if state["step"] == "ask_size":
        if incoming_msg.upper() in products[state["product"]]["sizes"]:
            state["size"] = incoming_msg.upper()
            state["step"] = "ask_address"
            msg.body("Send name and address (Name, Address)")
        else:
            msg.body("Invalid size")
        return str(resp)

    # ADDRESS → SAVE
    if state["step"] == "ask_address":
        parts = incoming_msg.split(",", 1)

        name = parts[0].strip()
        address = parts[1].strip() if len(parts) > 1 else ""

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

    msg.body("Send product like 'black shirt'")
    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
