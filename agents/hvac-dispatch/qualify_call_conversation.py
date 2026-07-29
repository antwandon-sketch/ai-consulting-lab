import json
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

SYSTEM_PROMPT = """You are a dispatcher for a home services company that handles HVAC, \
plumbing, electrical, and roofing calls. A transcript of what the caller said will be \
provided. Analyze it and extract structured information to help the dispatcher decide \
how to handle the call.

If you do NOT have enough information to confidently determine job_type and urgency, \
do not guess. Instead, respond with ONLY a single short clarifying question (plain text, \
no JSON) that would help you determine the job type and urgency.

If you DO have enough information, respond with ONLY a JSON object (no other text) with \
exactly these fields:
- "is_emergency": true or false — true if this poses immediate danger or major property \
damage (e.g. gas leak, electrical fire risk, burst pipe flooding a home, no heat in \
freezing weather).
- "job_type": a short string describing the job (e.g. "AC repair", "burst pipe", \
"electrical outage").
- "urgency": one of "low", "medium", "high", "emergency".
- "summary": a one-sentence summary of the issue.
- "suggested_action": what the business should do next (e.g. "dispatch today", \
"schedule within 48 hours", "schedule next available").

Below are reference examples ONLY, illustrating the expected output format. They are not \
part of the real conversation with the current caller — do not treat them as prior turns.

--- Example 1: emergency ---
Transcript: "I smell gas near my furnace and it's getting stronger, I don't know what to do"
Correct output:
{"is_emergency": true, "job_type": "gas leak", "urgency": "emergency", "summary": "Caller smells a strengthening gas odor near their furnace.", "suggested_action": "Instruct caller to leave the house and dispatch a technician immediately."}

--- Example 2: routine ---
Transcript: "My kitchen faucet has had a slow drip for about a week, I'd like to get it fixed"
Correct output:
{"is_emergency": false, "job_type": "faucet repair", "urgency": "low", "summary": "Caller has a slow-dripping kitchen faucet that has persisted for about a week.", "suggested_action": "Schedule next available appointment."}

--- Example 3: ambiguous, requires a follow-up question ---
Transcript: "uh yeah hi, something's wrong with my thing outside, the box, I don't know, it's making a noise"
Correct output (a clarifying question, not JSON):
What kind of outdoor unit is it — an AC/HVAC condenser, an electrical panel, or something else — and what kind of noise is it making?
"""

MAX_EXCHANGES = 4


def get_reply(client, history):
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=history,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def classify_reply(raw_text):
    """Return ("json", dict), ("question", str), or ("error", str)."""
    stripped = strip_code_fence(raw_text)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return "json", parsed

    text = raw_text.strip()
    # A response that looks like it was trying to be JSON (starts with a
    # brace or a code fence) but failed to parse is an error, not a question.
    if text.startswith("{") or text.startswith("```"):
        return "error", raw_text
    if text:
        return "question", text
    return "error", raw_text


def print_qualification(result):
    print("=== Call Qualification ===")
    print(f"Emergency:       {result.get('is_emergency')}")
    print(f"Job type:        {result.get('job_type')}")
    print(f"Urgency:         {result.get('urgency')}")
    print(f"Summary:         {result.get('summary')}")
    print(f"Suggested action: {result.get('suggested_action')}")


def main():
    client = Anthropic()
    history = []

    caller_input = input("Caller: ")
    history.append({"role": "user", "content": caller_input})

    for exchange in range(MAX_EXCHANGES):
        raw_text = get_reply(client, history)
        kind, payload = classify_reply(raw_text)

        if kind == "json":
            print_qualification(payload)
            return

        if kind == "error":
            print("Something went wrong reading the dispatcher's response "
                  "(it wasn't valid JSON or a clear question).")
            print("Raw response for reference:")
            print(raw_text)
        else:
            print(f"Dispatcher: {payload}")

        history.append({"role": "assistant", "content": raw_text})

        caller_input = input("Caller: ")
        history.append({"role": "user", "content": caller_input})

    print("Reached maximum exchanges without a confident qualification.")
    print("Raw last reply:")
    print(raw_text)
    sys.exit(1)


if __name__ == "__main__":
    main()
