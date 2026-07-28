import json
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

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


def main():
    if len(sys.argv) < 2:
        print('Usage: python qualify_call.py "<call transcript>"')
        sys.exit(1)

    transcript = " ".join(sys.argv[1:])

    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        print("Error: model did not return valid JSON.")
        print("Raw response:")
        print(raw_text)
        sys.exit(1)

    print("=== Call Qualification ===")
    print(f"Emergency:       {result.get('is_emergency')}")
    print(f"Job type:        {result.get('job_type')}")
    print(f"Urgency:         {result.get('urgency')}")
    print(f"Summary:         {result.get('summary')}")
    print(f"Suggested action: {result.get('suggested_action')}")


if __name__ == "__main__":
    main()
