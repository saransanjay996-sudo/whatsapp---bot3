from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import os
import json

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

# 📊 Google Sheets Save Function (FIXED)
def save_to_sheet(data):
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        creds_json = os.environ.get("GOOGLE_CREDS")
        creds_dict = json.loads(creds_json)

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key("19rCrD3KnpL9yqP9WioohMSi173NZQ1i1i7RAdj2arTs").sheet1
        sheet.append_row(data)

    except Exception as e:
        print("Sheet error:", e)


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

    # Initialize user
    if phone not in user_state:
        user_state[phone] = {"step": None, "product": None}

    state = user_state[phone]

    print("STEP:", state["step"], "MSG:", incoming_msg)

    # ❌ CANCEL
    if incoming_msg in ["cancel", "stop", "exit"]:
        if state["step"] is None:
            msg.body("No active order to cancel.")
        else:
            user_state[phone] = {"step": None, "product": None}
            msg.body("Order cancelled ❌\nYou can start again anytime.")
        return str(resp)

    # 🔍 Detect product
    found_product = None
    for product in products:
        if product in incoming_msg:
            found_product = product
            state["product"] = product
            break

    # 🛒 Order intent
    if "want" in incoming_msg or "buy" in incoming_msg:
        if state["product"]:
            state["step"] = "ask_size"
            msg.body(
                f"{state['product'].title()} is available. Which size do you want? ({', '.join(products[state['product']]['sizes'])})"
            )
        else:
            msg.body("Please mention the product name.")
        return str(resp)

    # 📏 Ask size
    if state["step"] == "ask_size":
        if incoming_msg.upper() in products[state["product"]]["sizes"]:
            state["size"] = incoming_msg.upper()
            state["step"] = "ask_address"
            msg.body("Please share your name and address (Example: Name, Address-000000)")
        else:
            msg.body("Invalid size. Please enter correct size.")
        return str(resp)

    # 📦 Confirm order + Save to Google Sheets
    if state["step"] == "ask_address":
        parts = incoming_msg.split(",", 1)

        if len(parts) == 2:
            name = parts[0].strip()
            address = parts[1].strip()
        else:
            name = incoming_msg.strip()
            address = ""

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        # ✅ FIX: Use function instead of undefined sheet
        save_to_sheet([
            name,
            phone,
            state["product"],
            state["size"],
            address,
            date,
            time,
            products[state["product"]]["delivery"]
        ])

        msg.body(
            f"Order confirmed ✅\n"
            f"Product: {state['product'].title()}\n"
            f"Size: {state['size']}\n"
            f"Delivery: {products[state['product']]['delivery']}"
        )

        user_state[phone] = {"step": None, "product": None}
        return str(resp)

    # 💡 Product Q&A
    if found_product:
        product_data = products[found_product]

        if "price" in incoming_msg:
            msg.body(
                f"{found_product.title()} price is {product_data['price']}. Available sizes: {', '.join(product_data['sizes'])}. Want to order?"
            )

        elif "size" in incoming_msg:
            msg.body(
                f"{found_product.title()} sizes: {', '.join(product_data['sizes'])}. Which size do you want?"
            )

        elif "delivery" in incoming_msg:
            msg.body(
                f"{found_product.title()} delivery time: {product_data['delivery']}. Want to order?"
            )

        else:
            msg.body(
                f"{found_product.title()} costs {product_data['price']} and is available in {', '.join(product_data['sizes'])}. Want to order?"
            )

    else:
        msg.body("Please mention product like 'black shirt' or 'white tshirt'.")

    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
