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

# 👤 State
user_state = {}

# 🔗 DB Connection
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')

# 🧱 Create table
def init_db():
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

# 💾 Save
def save_to_db(data):
    try:
        print("🔥 TRYING TO SAVE:", data)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO orders (name, phone, product, size, address, date, time, delivery)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, data)

        conn.commit()

        cur.close()
        conn.close()

        print("✅ SAVED SUCCESSFULLY")

    except Exception as e:
        import traceback
        print("❌ SAVE FAILED:")
        print(traceback.format_exc())

# 🔧 Force DB init
@app.route("/initdb")
def force_init():
    init_db()
    return "DB Initialized"

# 🏠 Home
@app.route("/")
def home():
    return "Bot running"

# 📦 View Orders
@app.route("/orders")
def view_orders():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return "No orders yet"

        output = ""
        for r in rows:
            output += f"""
ID: {r[0]}
Name: {r[1]}
Phone: {r[2]}
Product: {r[3]}
Size: {r[4]}
Address: {r[5]}
Date: {r[6]}
Time: {r[7]}
Delivery: {r[8]}
-------------------------
"""
        return output

    except Exception as e:
        import traceback
        return traceback.format_exc()

# 🤖 Webhook
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

    print("MSG:", incoming_msg, "| STATE:", state)

    # CANCEL
    if incoming_msg in ["cancel", "stop"]:
        user_state[phone] = {"step": None, "product": None, "size": None}
        msg.body("Order cancelled ❌")
        return str(resp)

    # PRODUCT DETECT
    found_product = None
    for p in products:
        if p in incoming_msg:
            found_product = p
            break

    # START ORDER
    if state["step"] is None and found_product:
        state["product"] = found_product
        state["step"] = "size"
        msg.body(f"{found_product.title()} available.\nSizes: {', '.join(products[found_product]['sizes'])}\nEnter size:")
        return str(resp)

    # SIZE
    if state["step"] == "size":
        size = incoming_msg.upper()

        if size in products[state["product"]]["sizes"]:
            state["size"] = size
            state["step"] = "address"
            msg.body("Send name and address")
        else:
            msg.body("Invalid size. Try again.")
        return str(resp)

    # ADDRESS → SAVE
    if state["step"] == "address":
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

Product: {state['product']}
Size: {state['size']}
Delivery: {products[state['product']]['delivery']}"""
        )

        user_state[phone] = {"step": None, "product": None, "size": None}
        return str(resp)

    msg.body("Send product name like 'black shirt'")
    return str(resp)


if __name__ == "__main__":
    init_db()  # IMPORTANT
    app.run(host="0.0.0.0", port=5000)
