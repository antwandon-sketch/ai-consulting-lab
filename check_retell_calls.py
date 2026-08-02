"""
Pulls full call detail (transcript + tool call arguments + tool call results)
for the 5 test calls from today via Retell's API, and prints exactly what
was sent to create_booking and what came back.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("RETELL_API_KEY")
if not API_KEY:
    raise SystemExit(
        "RETELL_API_KEY not found in .env. Add it (Retell dashboard -> Settings -> API Keys) and re-run."
    )

CALL_IDS = [
    "call_4de07e6a8c796f101ff67d74155",  # Successful - baseline comparison
    "call_b6309e124a03fd2267f35977e33",  # Unsuccessful
    "call_5d3d05ac1b1f02bf06d38b3a18c",  # Unsuccessful
    "call_9011ece423a3182b2930a52bb29",  # Unsuccessful
    "call_7d1c28f6c0baaa9a912ea34980e",  # Unsuccessful
]

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

for call_id in CALL_IDS:
    print("=" * 80)
    print(f"CALL: {call_id}")
    print("=" * 80)

    resp = requests.get(
        f"https://api.retellai.com/v2/get-call/{call_id}",
        headers=HEADERS,
    )

    if resp.status_code != 200:
        print(f"  FAILED TO FETCH: {resp.status_code} - {resp.text}")
        continue

    data = resp.json()

    print(f"  call_successful: {data.get('call_analysis', {}).get('call_successful')}")
    print(f"  disconnection_reason: {data.get('disconnection_reason')}")

    transcript = data.get("transcript_with_tool_calls", []) or data.get("transcript_object", [])
    found_tool_call = False
    for turn in transcript:
        role = turn.get("role")
        if role == "tool_call_invocation":
            found_tool_call = True
            print("\n  --- TOOL CALL SENT ---")
            print(f"  name: {turn.get('name')}")
            print(f"  arguments: {json.dumps(turn.get('arguments'), indent=2)}")
        elif role == "tool_call_result":
            print("\n  --- TOOL CALL RESULT ---")
            print(f"  content: {turn.get('content')}")

    if not found_tool_call:
        print("\n  (no tool call invocation found in transcript for this call)")

    print()

print("=" * 80)
print("Done. Scroll up to compare the successful call's arguments/result")
print("against the 4 unsuccessful ones.")
print("=" * 80)
