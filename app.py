"""
app.py — Flask application entry point.

DO NOT MOVE this file or rename the `app` object — Render's start command
(gunicorn app:app) depends on this exact path and name.

Route logic lives in routes/dispatch.py (qualification + booking) and
routes/billing.py (Stripe checkout + webhook) — this file just wires them
together.
"""

import os

from flask import Flask

from routes.billing import billing_bp
from routes.dispatch import dispatch_bp

app = Flask(__name__)
app.register_blueprint(dispatch_bp)
app.register_blueprint(billing_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
