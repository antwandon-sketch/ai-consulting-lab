"""
routes/billing.py — Stripe checkout and webhook handling.
"""

import stripe
from flask import Blueprint, jsonify, redirect, request

from config import BASE_URL, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET
from db import save_payment

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/pricing", methods=["GET"])
def pricing():
    """Minimal pricing page with a Subscribe button that starts Stripe Checkout."""
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


@billing_bp.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """Starts a Stripe Checkout session and redirects the customer to it."""
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{BASE_URL}/success",
        cancel_url=f"{BASE_URL}/cancel",
    )
    return redirect(session.url)


@billing_bp.route("/success", methods=["GET"])
def success():
    return "Payment successful. Thank you for subscribing!"


@billing_bp.route("/cancel", methods=["GET"])
def cancel():
    return "Checkout was cancelled."


@billing_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Stripe webhook receiver. Verifies the signature, then persists confirmed
    checkout sessions to Neon via save_payment (idempotent — see db.py).
    """
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
