"""
config.py — centralized configuration and shared client instances.

Loaded once, imported by both app.py and the route blueprints, so there's a
single source of truth for API keys, Stripe configuration, and the Anthropic
client rather than each module reaching into os.environ independently.
"""

import os

import stripe
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

APP_SECRET_KEY: str = os.environ["APP_SECRET_KEY"]

STRIPE_SECRET_KEY: str = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET: str = os.environ["STRIPE_WEBHOOK_SECRET"]
STRIPE_PRICE_ID: str = os.environ.get("STRIPE_PRICE_ID", "price_1TyHdI3ziIQD0jW77H5AVAaP")

stripe.api_key = STRIPE_SECRET_KEY

# Base URL Stripe redirects back to after checkout. Defaults to local dev —
# set BASE_URL in Render's Environment tab to the real production URL
# (https://havoc-qualifier-api.onrender.com), or checkout will try to send
# real customers back to an unreachable localhost address.
BASE_URL: str = os.environ.get("BASE_URL", "http://127.0.0.1:5001")

# Owner-notification email sent after each successful /book call (see
# routes/dispatch.py) — SMTP_USER/SMTP_PASSWORD are Gmail credentials (an
# app password, not the account password). All three are optional at the
# env level: if any are missing, the booking still succeeds and
# routes/dispatch.py logs a warning instead of sending.
OWNER_NOTIFY_EMAIL: str | None = os.environ.get("OWNER_NOTIFY_EMAIL")
SMTP_USER: str | None = os.environ.get("SMTP_USER")
SMTP_PASSWORD: str | None = os.environ.get("SMTP_PASSWORD")

anthropic_client = Anthropic()
