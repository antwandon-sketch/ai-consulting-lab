import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from anthropic import Anthropic

load_dotenv()

app = Flask(__name__)
client = Anthropic()

APP_SECRET_KEY = os.environ["APP_SECRET_KEY"]

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
