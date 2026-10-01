"""
routes/dispatch.py — call qualification and booking endpoints.
"""

import json
import logging
import smtplib
import threading
from email.message import EmailMessage
from typing import Any

from flask import Blueprint, jsonify, request

from config import (
    APP_SECRET_KEY,
    OWNER_NOTIFY_EMAIL,
    SMTP_PASSWORD,
    SMTP_USER,
    anthropic_client,
)
from db import save_booking

logger = logging.getLogger(__name__)

dispatch_bp = Blueprint("dispatch", __name__)

# Gmail account the owner-notification email is sent from (see notify_owner
# below). Must match the account SMTP_USER/SMTP_PASSWORD authenticate as.
NOTIFY_SENDER_EMAIL = "allrhodesmedia@gmail.com"

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

REQUIRED_BOOKING_FIELDS = [
    "job_type",
    "urgency",
    "is_emergency",
    "summary",
    "suggested_action",
    "customer_name",
    "service_address",
    "business_name",
]

# Values the model has been caught sending to satisfy a "required" schema
# field without actually having real information — see PROJECT.md's
# "Hard-Won Lessons" for the 2026-07-30 incident this guards against.
PLACEHOLDER_VALUES = {
    "unknown", "n/a", "na", "none", "tbd",
    "pending", "null", "not provided", "not available",
}


def qualify(transcript: str) -> dict[str, Any]:
    """
    Send a call transcript to Claude and return a structured qualification:
    job type, urgency, emergency status, a one-sentence summary, and a
    suggested next action.

    Raises json.JSONDecodeError if the model's response isn't valid JSON.
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return json.loads(raw_text)


def _check_api_key() -> bool:
    return request.headers.get("X-API-Key") == APP_SECRET_KEY


def _build_notification_email(data: dict[str, Any], booking_id: int) -> EmailMessage:
    is_emergency = str(data.get("is_emergency", "")).strip().lower() == "true"
    subject_prefix = "EMERGENCY: " if is_emergency else ""
    subject = (
        f"{subject_prefix}New booking — "
        f"{data.get('job_type', '')} for {data.get('customer_name', '')}"
    )

    body = "\n".join([
        f"Booking ID: {booking_id}",
        f"Business: {data.get('business_name', '')}",
        f"Customer: {data.get('customer_name', '')}",
        f"Service address: {data.get('service_address', '')}",
        f"Job type: {data.get('job_type', '')}",
        f"Urgency: {data.get('urgency', '')}",
        f"Emergency: {data.get('is_emergency', '')}",
        f"Summary: {data.get('summary', '')}",
        f"Suggested action: {data.get('suggested_action', '')}",
    ])

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = NOTIFY_SENDER_EMAIL
    message["To"] = OWNER_NOTIFY_EMAIL
    message.set_content(body)
    return message


def _send_booking_notification_email(data: dict[str, Any], booking_id: int) -> None:
    """
    Sends the owner-notification email synchronously over Gmail's SMTP.
    Always called off the request thread (see notify_owner) so SMTP latency
    never delays the /book response Retell is waiting on during a live call.
    """
    message = _build_notification_email(data, booking_id)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)


def _run_in_background(fn) -> None:
    threading.Thread(target=fn, daemon=True).start()


def notify_owner(data: dict[str, Any], booking_id: int) -> None:
    """
    Fire-and-forget owner notification for a successful booking, so this
    product works against any client's scheduling software without a
    custom integration. Runs off the request thread and never raises: a
    notification problem (missing config, SMTP failure) is logged and
    swallowed rather than allowed to break a booking that already saved
    successfully.
    """
    if not (OWNER_NOTIFY_EMAIL and SMTP_USER and SMTP_PASSWORD):
        logger.warning(
            "Skipping owner notification email for booking %s: "
            "OWNER_NOTIFY_EMAIL, SMTP_USER, or SMTP_PASSWORD is not set.",
            booking_id,
        )
        return

    def _send():
        try:
            _send_booking_notification_email(data, booking_id)
        except Exception:
            logger.exception(
                "Failed to send owner notification email for booking %s.",
                booking_id,
            )

    _run_in_background(_send)


@dispatch_bp.route("/", methods=["GET"])
def index():
    """Basic health check — confirms the API is up."""
    return jsonify({"message": "API is running"})


@dispatch_bp.route("/qualify", methods=["POST"])
def qualify_route():
    """
    Qualify a raw call transcript via Claude. Expects JSON body:
    {"transcript": "..."}. Returns the structured qualification fields
    described in SYSTEM_PROMPT.
    """
    if not _check_api_key():
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


@dispatch_bp.route("/book", methods=["POST"])
def book():
    """
    Log a booking. This is the endpoint Retell's create_booking function
    calls once the voice agent has qualified a job and collected the
    caller's name and service address.

    Rejects the request (400) if any required field is missing, blank, or
    a known placeholder value (see PLACEHOLDER_VALUES) — a hard backstop
    against the model satisfying a "required" schema constraint without
    actually collecting real information.
    """
    if not _check_api_key():
        return jsonify({"error": "Missing or invalid X-API-Key header."}), 401

    data = request.get_json(silent=True) or {}

    missing_fields = [
        field for field in REQUIRED_BOOKING_FIELDS
        if not str(data.get(field, "")).strip()
        or str(data.get(field, "")).strip().lower() in PLACEHOLDER_VALUES
    ]
    if missing_fields:
        return jsonify(
            {"error": f"Missing required field(s): {', '.join(missing_fields)}."}
        ), 400

    data["caller_number"] = data.get("caller_number") or ""
    booking_id = save_booking(data)

    notify_owner(data, booking_id)

    return jsonify({"status": "booked", "message": "Booking logged", "booking_id": booking_id})
