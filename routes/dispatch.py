"""
routes/dispatch.py — call qualification and booking endpoints.
"""

import json
from typing import Any

from flask import Blueprint, jsonify, request

from config import APP_SECRET_KEY, anthropic_client
from db import save_booking

dispatch_bp = Blueprint("dispatch", __name__)

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

    return jsonify({"status": "booked", "message": "Booking logged", "booking_id": booking_id})
