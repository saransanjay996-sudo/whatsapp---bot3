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

# 📊 Save to Google Sheet
def save_to_sheet(data):
    try:
        print("🚀 ENTERED save_to_sheet")

        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        import json
        import os

        creds_json = os.environ.get("GOOGLE_CREDS")

        print("🔑 CREDS RAW:", creds_json[:50] if creds_json else "None")

        if not creds_json:
            print("❌ GOOGLE_CREDS missing")
            return

        creds_dict = json.loads(creds_json)
        print("✅ JSON LOADED")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        print("✅ CREDS OBJECT CREATED")

        client = gspread.authorize(creds)
        print("✅ CLIENT AUTHORIZED")

        sheet = client.open_by_key("19rCrD3KnpL9yqP9WioohMSi173NZQ1i1i7RAdj2arTs").sheet1
        print("✅ SHEET OPENED")

        sheet.append_row(data)
        print("🔥 DATA SUCCESSFULLY SAVED:", data)

    except Exception as e:
        import traceback
        print("❌ FULL ERROR BELOW:")
        print(traceback.format_exc())



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

    # Initialize state
    if phone not in user_state:
        user_state[phone] = {"step": None, "product": None, "size": None}

    state = user_state[phone]

    print("STATE:", state, "MSG:", incoming_msg)

    # ❌ CANCEL
    if incoming_msg in ["cancel", "stop", "exit"]:
        user_state[phone] = {"step": None, "product": None, "size": None}
        msg.body("Order cancelled ❌\nStart again anytime.")
        return str(resp)

    # 🔍 Detect product
    found_product = None
    for product in products:
        if product in incoming_msg:
            found_product = product
            break

    # 💡 Q&A MODE (if not in order flow)
    if state["step"] is None and found_product:
        p = products[found_product]

        if "price" in incoming_msg:
            msg.body(f"{found_product.title()} price is {p['price']}. Want to order?")
            return str(resp)

        elif "size" in incoming_msg:
            msg.body(f"{found_product.title()} sizes: {', '.join(p['sizes'])}.")
            return str(resp)

        elif "delivery" in incoming_msg:
            msg.body(f"{found_product.title()} delivery time: {p['delivery']}.")
            return str(resp)

        else:
            # Start order automatically
            state["product"] = found_product
            state["step"] = "ask_size"

            msg.body(
                f"{found_product.title()} is available.\nSizes: {', '.join(p['sizes'])}\nEnter size:"
            )
            return str(resp)

    # 🟢 STEP 1 → SIZE
    if state.get("step") == "ask_size" and state.get("product"):
        if incoming_msg.upper() in products[state["product"]]["sizes"]:
            state["size"] = incoming_msg.upper()
            state["step"] = "ask_address"

            msg.body("Send your name and address\nExample: xxxxxxx, xxxxxxxxxx - 000000")
        else:
            msg.body("Invalid size. Enter correct size (M, L, XL)")
        return str(resp)

    # 🟢 STEP 2 → ADDRESS → SAVE
    if state.get("step") == "ask_address" and state.get("product") and state.get("size"):
        parts = incoming_msg.split(",", 1)

        if len(parts) == 2:
            name = parts[0].strip()
            address = parts[1].strip()
        else:
            name = incoming_msg
            address = ""

        now = datetime.now()

        save_to_sheet([
            name,
            phone,
            state["product"],
            state["size"],
            address,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            products[state["product"]]["delivery"]
        ])

        msg.body(
            f"Order Confirmed ✅\n"
            f"Product: {state['product'].title()}\n"
            f"Size: {state['size']}\n"
            f"Delivery: {products[state['product']]['delivery']}"
        )

        user_state[phone] = {"step": None, "product": None, "size": None}
        return str(resp)

    # Default fallback
    msg.body("Send product name like 'black shirt' to start.")
    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
