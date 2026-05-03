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
            return "<h2>No orders yet</h2>"

        # 🧾 HTML TABLE
        html = """
        <html>
        <head>
            <title>Orders</title>
            <style>
                table {
                    border-collapse: collapse;
                    width: 100%;
                    font-family: Arial;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 10px;
                    text-align: left;
                }
                th {
                    background-color: #333;
                    color: white;
                }
                tr:nth-child(even) {
                    background-color: #f2f2f2;
                }
            </style>
        </head>
        <body>
            <h2>📦 Orders Dashboard</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Product</th>
                    <th>Size</th>
                    <th>Address</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Delivery</th>
                </tr>
        """

        for r in rows:
            html += f"""
            <tr>
                <td>{r[0]}</td>
                <td>{r[1]}</td>
                <td>{r[2]}</td>
                <td>{r[3]}</td>
                <td>{r[4]}</td>
                <td>{r[5]}</td>
                <td>{r[6]}</td>
                <td>{r[7]}</td>
                <td>{r[8]}</td>
            </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html

    except Exception as e:
        return str(e)

# 🏠 home
@app.route("/")
def home():
    return "Bot is running"

@app.route("/webhook", methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    user_number = request.values.get('From')
    phone = user_number.replace("whatsapp:", "")

    resp = MessagingResponse()
    msg = resp.message()

    if phone not in user_state:
        user_state[phone] = {}

    state = user_state[phone]

    print("MSG:", incoming_msg, "STATE:", state)

    # CANCEL
    if incoming_msg in ["cancel", "stop", "exit"]:
        user_state[phone] = {}
        msg.body("Order cancelled ❌")
        return str(resp)

    # 🔴 DIRECT ORDER DETECTION (FAILSAFE)
    if "," in incoming_msg and len(incoming_msg) > 5:
        print("🔥 FORCED FINAL STEP")

        parts = incoming_msg.split(",", 1)
        name = parts[0].strip()
        address = parts[1].strip()

        product = state.get("product", "black shirt")  # fallback
        size = state.get("size", "M")  # fallback

        now = datetime.now()

        data = [
            name,
            phone,
            product,
            size,
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            products.get(product, {}).get("delivery", "3-5 days")
        ]

        save_to_db(data)

        msg.body(
            f"""Order Confirmed ✅

Product: {product}
Size: {size}
Delivery: {products.get(product, {}).get("delivery", "3-5 days")}"""
        )

        user_state[phone] = {}
        return str(resp)

    # STEP 1: PRODUCT
    for p in products:
        if p in incoming_msg:
            state["product"] = p
            msg.body(f"{p.title()} selected. Enter size: {', '.join(products[p]['sizes'])}")
            return str(resp)

    # STEP 2: SIZE
    if incoming_msg.upper() in ["S", "M", "L", "XL"]:
        state["size"] = incoming_msg.upper()
        msg.body("Send name and address")
        return str(resp)

    msg.body("Send product like 'black shirt' or 'white tshirt'")
    return str(resp)
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
