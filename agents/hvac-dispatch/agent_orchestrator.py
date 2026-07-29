import json
import os
import random
import string
import sys
from datetime import datetime

import chromadb
import voyageai
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "hvac_company_docs"
EMBED_MODEL = "voyage-3.5"
N_RESULTS = 2

BOOKINGS_LOG_PATH = "bookings.log"
SMS_LOG_PATH = "sms.log"
MAX_EXCHANGES = 4

MODEL = "claude-sonnet-5"

client = Anthropic()

# ---------------------------------------------------------------------------
# Qualifier agent — sees the conversation + retrieved facts. Knows nothing
# about scheduling or SMS notifications.
# ---------------------------------------------------------------------------

QUALIFIER_SYSTEM_PROMPT = """You are a dispatcher for a home services company that handles HVAC, \
plumbing, electrical, and roofing calls. Each caller turn is provided in this format:

Relevant company info:
- <fact retrieved from the company knowledge base>
- <fact retrieved from the company knowledge base>

Caller: <what the caller actually said>

The "Relevant company info" facts are retrieved from the company's knowledge base based on \
the caller's latest message. They are for your reference only — they are not something the \
caller said. Use them to answer real factual questions (hours, pricing, service area, \
emergency policy) accurately. If the retrieved facts don't address the caller's question, say \
you're not sure rather than guessing — never fabricate a detail not present in the retrieved \
info.

Your job on every turn is to analyze the conversation so far and extract structured \
information to help the dispatcher decide how to handle the call, while also answering any \
factual question the caller asked.

If you do NOT have enough information to confidently determine job_type and urgency, do not \
guess. Instead, respond with plain text (no JSON): first answer any factual question the \
caller asked using the retrieved facts, then ask ONE short clarifying question that would help \
you determine the job type and urgency. If there's no factual question, just ask the \
clarifying question.

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

Below are reference examples ONLY, illustrating the expected format. They are not part of the \
real conversation with the current caller — do not treat them as prior turns.

--- Example 1: emergency ---
Relevant company info:
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: I smell gas near my furnace and it's getting stronger, I don't know what to do
Correct output:
{"is_emergency": true, "job_type": "gas leak", "urgency": "emergency", "summary": "Caller smells a strengthening gas odor near their furnace.", "suggested_action": "Instruct caller to leave the house and dispatch a technician immediately."}

--- Example 2: routine ---
Relevant company info:
- All repairs and installations are backed by a 1-year labor warranty in addition to the \
manufacturer's parts warranty.

Caller: My kitchen faucet has had a slow drip for about a week, I'd like to get it fixed
Correct output:
{"is_emergency": false, "job_type": "faucet repair", "urgency": "low", "summary": "Caller has a slow-dripping kitchen faucet that has persisted for about a week.", "suggested_action": "Schedule next available appointment."}

--- Example 3: ambiguous, requires a follow-up question ---
Relevant company info:
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: uh yeah hi, something's wrong with my thing outside, the box, I don't know, it's making a noise
Correct output (plain text, not JSON):
What kind of outdoor unit is it — an AC/HVAC condenser, an electrical panel, or something else — and what kind of noise is it making?

--- Example 4: factual question, still needs a clarifying question ---
Relevant company info:
- Our regular business hours are Monday through Friday, 8:00 AM to 6:00 PM, and Saturday 9:00 \
AM to 2:00 PM.
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: Are you open right now? Also my heater just stopped working.
Correct output (plain text, not JSON):
We're open Monday through Friday 8am-6pm and Saturday 9am-2pm, but we also run 24/7 emergency service for no-heat situations. Is the heater completely out, and how cold is it inside your home right now?
"""


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
    if text.startswith("{") or text.startswith("```"):
        return "error", raw_text
    if text:
        return "question", text
    return "error", raw_text


def qualifier_agent(history, retrieved_facts):
    """Multi-turn qualifying logic. `history` holds the raw conversation (caller and
    assistant turns, no retrieval text baked in). `retrieved_facts` are the facts
    retrieved for the caller's latest message — spliced into the request just for
    this call, not permanently stored in `history`.

    Returns a clarifying question (str) or a qualified job dict.
    """
    facts_block = "\n".join(f"- {fact}" for fact in retrieved_facts)
    last_caller_message = history[-1]["content"]
    augmented_last_turn = {
        "role": "user",
        "content": f"Relevant company info:\n{facts_block}\n\nCaller: {last_caller_message}",
    }
    request_messages = history[:-1] + [augmented_last_turn]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"effort": "low"},
        system=QUALIFIER_SYSTEM_PROMPT,
        messages=request_messages,
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    history.append({"role": "assistant", "content": raw_text})

    kind, payload = classify_reply(raw_text)
    if kind == "json":
        return payload
    if kind == "question":
        return payload
    return "Sorry, could you tell me a bit more about the issue?"


# ---------------------------------------------------------------------------
# Scheduling agent — sees ONLY the qualified job dict. Knows nothing about
# the raw conversation, retrieved facts, or SMS notifications.
# ---------------------------------------------------------------------------

SCHEDULING_SYSTEM_PROMPT = """You are a scheduling assistant for a home services company. \
You will be given a job's urgency and job type. Propose a short, natural-language slot \
description for when a technician will arrive, based on urgency:
- "emergency": today, within a tight same-day window (e.g. "today between 2-4pm")
- "high": within 48 hours
- "medium": within the next few days
- "low": next available slot, no rush

Respond with ONLY the slot description text — nothing else, no JSON, no extra commentary."""


def generate_booking_id():
    return "BK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def log_booking(qualified_job, booking):
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = (
        f"{timestamp} | booking_id={booking['booking_id']} | "
        f"job_type={qualified_job.get('job_type')} | "
        f"urgency={qualified_job.get('urgency')} | "
        f"is_emergency={qualified_job.get('is_emergency')} | "
        f"summary={qualified_job.get('summary')} | "
        f"suggested_action={qualified_job.get('suggested_action')} | "
        f"slot={booking['slot_description']}\n"
    )
    with open(BOOKINGS_LOG_PATH, "a") as f:
        f.write(line)


def scheduling_agent(qualified_job):
    """Takes only the qualified job dict — no conversation, no facts."""
    prompt = (
        f"job_type: {qualified_job['job_type']}\n"
        f"urgency: {qualified_job['urgency']}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        output_config={"effort": "low"},
        system=SCHEDULING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    slot_description = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    booking = {
        "slot_description": slot_description,
        "booking_id": generate_booking_id(),
    }
    log_booking(qualified_job, booking)
    return booking


# ---------------------------------------------------------------------------
# Notification agent — sees ONLY the qualified job dict and the booking dict.
# Knows nothing about the raw conversation, retrieved facts, or scheduling logic.
# ---------------------------------------------------------------------------

NOTIFICATION_SYSTEM_PROMPT = """You write short SMS confirmation messages for a home \
services company. You will be given a job type and a scheduled slot description. Write a \
friendly, concise SMS (2-3 sentences max) confirming the appointment to the customer, \
referencing the job type and the slot description naturally. Do not invent details (price, \
technician name, phone numbers) that weren't given to you. Respond with ONLY the SMS text."""


def log_sms(sms_text):
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(SMS_LOG_PATH, "a") as f:
        f.write(f"{timestamp} | {sms_text}\n")


def notification_agent(qualified_job, booking):
    """Takes only the qualified job and booking dicts — no conversation, no facts,
    no scheduling reasoning."""
    prompt = (
        f"job_type: {qualified_job['job_type']}\n"
        f"slot_description: {booking['slot_description']}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        output_config={"effort": "low"},
        system=NOTIFICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    sms_text = "".join(block.text for block in response.content if block.type == "text").strip()

    log_sms(sms_text)
    print(f"SMS to customer: {sms_text}")
    return sms_text


# ---------------------------------------------------------------------------
# Orchestrator — wires the three narrow agents together. Owns the retrieval
# step and the conversation loop; delegates qualification, scheduling, and
# notification to agents that each see only what they need.
# ---------------------------------------------------------------------------

def retrieve_relevant_facts(voyage_client, collection, query):
    query_embedding = voyage_client.embed(
        [query], model=EMBED_MODEL, input_type="query"
    ).embeddings[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=N_RESULTS)
    return results["documents"][0]


def main():
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    history = []

    for exchange in range(MAX_EXCHANGES):
        caller_input = input("Caller: ")
        facts = retrieve_relevant_facts(voyage_client, collection, caller_input)
        history.append({"role": "user", "content": caller_input})

        print("[Orchestrator -> Qualifier] conversation so far + retrieved facts:")
        print(f"    facts: {facts}")
        result = qualifier_agent(history, facts)

        if isinstance(result, dict):
            print("[Qualifier -> Orchestrator] call is qualified:")
            print(f"    {json.dumps(result)}")

            print("-- Qualified --")
            print(f"  job_type:         {result.get('job_type')}")
            print(f"  urgency:          {result.get('urgency')}")
            print(f"  is_emergency:     {result.get('is_emergency')}")
            print(f"  summary:          {result.get('summary')}")
            print(f"  suggested_action: {result.get('suggested_action')}")

            print("[Orchestrator -> Scheduler] sending ONLY the qualified job dict:")
            print(f"    {json.dumps({'job_type': result['job_type'], 'urgency': result['urgency']})}")
            booking = scheduling_agent(result)
            print("[Scheduler -> Orchestrator] booking created:")
            print(f"    {json.dumps(booking)}")
            print(f"Booking created: {booking['booking_id']} - {booking['slot_description']}")

            print("[Orchestrator -> Notifier] sending ONLY job_type + slot_description:")
            print(f"    {json.dumps({'job_type': result['job_type'], 'slot_description': booking['slot_description']})}")
            notification_agent(result, booking)
            print("[Notifier -> Orchestrator] SMS drafted and logged to sms.log")
            return

        print("[Qualifier -> Orchestrator] not enough info yet, asked a clarifying question")
        print(f"Dispatcher: {result}")

    print("Reached maximum exchanges without qualifying the call.")
    sys.exit(1)


if __name__ == "__main__":
    main()
