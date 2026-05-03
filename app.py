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
    print("🚀 WEBHOOK STARTED")

    incoming_msg = request.values.get('Body')
    user_number = request.values.get('From')

    if not incoming_msg or not user_number:
        return "OK"

    incoming_msg = incoming_msg.strip().lower()
    phone = user_number.replace("whatsapp:", "")

    resp = MessagingResponse()
    msg = resp.message()

    print("📩 MSG:", incoming_msg)

    # 🛍️ PRODUCT DATABASE
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

    # ❌ CANCEL
    if incoming_msg in ["cancel", "stop", "exit"]:
        msg.body("Order cancelled ❌")
        return str(resp)

    # 💥 PRICE / INFO QUERY
    for product in products:
        if product in incoming_msg:

            data = products[product]

            if "price" in incoming_msg:
                msg.body(f"{product.title()} price is {data['price']}")
                return str(resp)

            elif "size" in incoming_msg:
                msg.body(f"{product.title()} sizes: {', '.join(data['sizes'])}")
                return str(resp)

            elif "delivery" in incoming_msg:
                msg.body(f"{product.title()} delivery: {data['delivery']}")
                return str(resp)

            else:
                msg.body(
                    f"{product.title()} costs {data['price']}.\n"
                    f"Sizes: {', '.join(data['sizes'])}\n"
                    f"Type size to order."
                )
                return str(resp)

    # 💥 SIZE STEP
    if incoming_msg.upper() in ["S", "M", "L", "XL"]:
        msg.body("Send your name and address (Name, Address)")
        return str(resp)

    # 💥 FINAL ORDER (SAVE)
    if "," in incoming_msg:
        print("🔥 ORDER DETECTED")

        parts = incoming_msg.split(",", 1)
        name = parts[0].strip()
        address = parts[1].strip()

        now = datetime.now()

        save_to_db([
            name,
            phone,
            "black shirt",   # default (can upgrade later)
            "M",
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            "3-5 days"
        ])

        print("✅ SAVED")

        msg.body(
            "Order Confirmed ✅\n"
            "Product: Black Shirt\n"
            "Size: M\n"
            "Delivery: 3-5 days"
        )
        return str(resp)

    # 💡 DEFAULT
    msg.body(
        "Send:\n"
        "- 'black shirt price'\n"
        "- 'white tshirt size'\n"
        "- or type product name to order"
    )

    return str(resp)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
