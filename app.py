import json
import os
from datetime import datetime, timezone

import stripe
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request
from anthropic import Anthropic

load_dotenv()

app = Flask(__name__)
client = Anthropic()

APP_SECRET_KEY = os.environ["APP_SECRET_KEY"]

STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
stripe.api_key = STRIPE_SECRET_KEY
STRIPE_PRICE_ID = "price_1TyHdI3ziIQD0jW77H5AVAaP"

STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

SYSTEM_PROMPT = """You are a dispatcher for a home services company that handles HVAC, \
plumbing, electrical, and roofing calls. A transcript of what the caller said will be \
provided. Analyze it and extract structured information to help the dispatcher decide \
how to handle the call.

Respond with ONLY a JSON object (no other text) with exactly these fields:
- "is_emergency": true or false — true if this poses immediate danger or major property \
damage (e.g. gas leak, electrical fire risk, burst pipe flooding a home, no heat in \
freezing weather).
- "job_type": a short string describing the job (e.g. "AC repair", "burst pipe", \
"electrical outage").
- "urgency": one of "low", "medium", "high", "emergency".
- "summary": a one-sentence summary of the issue.
- "suggested_action": what the business should do next (e.g. "dispatch today", \
"schedule within 48 hours", "schedule next available").
"""


def qualify(transcript):
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return json.loads(raw_text)


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "API is running"})


@app.route("/qualify", methods=["POST"])
def qualify_route():
    if request.headers.get("X-API-Key") != APP_SECRET_KEY:
        return jsonify({"error": "Missing or invalid X-API-Key header."}), 401

    data = request.get_json(silent=True) or {}
    transcript = data.get("transcript")

    if not transcript:
        return jsonify({"error": "Missing 'transcript' field in JSON body."}), 400

    try:
        result = qualify(transcript)
    except json.JSONDecodeError:
        return jsonify({"error": "Model did not return valid JSON."}), 502

    return jsonify(result)


from db import save_booking, save_payment


@app.route("/book", methods=["POST"])
def book():
    if request.headers.get("X-API-Key") != APP_SECRET_KEY:
        return jsonify({"error": "Missing or invalid X-API-Key header."}), 401

    data = request.get_json(silent=True) or {}

    required_fields = [
        "job_type",
        "urgency",
        "is_emergency",
        "summary",
        "suggested_action",
        "customer_name",
        "service_address",
        "business_name",
    ]
    PLACEHOLDER_VALUES = {"unknown", "n/a", "na", "none", "tbd", "pending", "null", "not provided", "not available"}
    missing_fields = [
        field for field in required_fields
        if not str(data.get(field, "")).strip()
        or str(data.get(field, "")).strip().lower() in PLACEHOLDER_VALUES
    ]
    if missing_fields:
        return jsonify(
            {"error": f"Missing required field(s): {', '.join(missing_fields)}."}
        ), 400

    caller_number = data.get("caller_number") or ""
    timestamp = datetime.now(timezone.utc).isoformat()

    data["caller_number"] = caller_number
    booking_id = save_booking(data)

    return jsonify({"status": "booked", "message": "Booking logged", "booking_id": booking_id})


@app.route("/pricing", methods=["GET"])
def pricing():
    return """
    <html>
      <body>
        <h1>Pricing</h1>
        <form action="/create-checkout-session" method="POST">
          <button type="submit">Subscribe</button>
        </form>
      </body>
    </html>
    """


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url="http://127.0.0.1:5001/success",
        cancel_url="http://127.0.0.1:5001/cancel",
    )
    return redirect(session.url)


@app.route("/success", methods=["GET"])
def success():
    return "Payment successful. Thank you for subscribing!"


@app.route("/cancel", methods=["GET"])
def cancel():
    return "Checkout was cancelled."


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    signature = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({"error": "Invalid signature."}), 400

    if event["type"] == "checkout.session.completed":
        session_id = event["data"]["object"]["id"]
        print(f"Payment confirmed for session {session_id} - activating client")
        save_payment(session_id)

    return jsonify({"received": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
