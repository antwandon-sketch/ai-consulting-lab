import os
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
MAX_EXCHANGES = 4

CREATE_BOOKING_TOOL = {
    "name": "create_booking",
    "description": (
        "Create a service booking once you have enough information to confidently "
        "determine the job type and urgency. Call this instead of asking another "
        "question once the call is qualified — do not call it while you still need "
        "to ask a clarifying question."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_issue": {
                "type": "string",
                "description": "A one-sentence summary of the issue the caller described.",
            },
            "job_type": {
                "type": "string",
                "description": (
                    'A short string describing the job (e.g. "AC repair", '
                    '"burst pipe", "electrical outage").'
                ),
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "medium", "high", "emergency"],
                "description": "The urgency level of the job.",
            },
            "suggested_action": {
                "type": "string",
                "description": (
                    'What the business should do next (e.g. "dispatch today", '
                    '"schedule within 48 hours", "schedule next available").'
                ),
            },
        },
        "required": ["customer_issue", "job_type", "urgency", "suggested_action"],
    },
}

SYSTEM_PROMPT = """You are a dispatcher for a home services company that handles HVAC, \
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

Your job on every turn is to decide whether you have enough information to qualify the call, \
while also answering any factual question the caller asked.

If you do NOT have enough information to confidently determine job_type and urgency, do not \
guess and do not call any tool. Instead, respond with plain text: first answer any factual \
question the caller asked using the retrieved facts, then ask ONE short clarifying question \
that would help you determine the job type and urgency. If there's no factual question, just \
ask the clarifying question.

If you DO have enough information, call the create_booking tool with the job details. You may \
say a brief sentence to the caller first (e.g. confirming you have what you need), but do not \
restate the booking details as text — the tool call itself carries them.

Below are reference examples ONLY, illustrating the expected behavior. They are not part of \
the real conversation with the current caller — do not treat them as prior turns.

--- Example 1: emergency, enough info to book ---
Relevant company info:
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: I smell gas near my furnace and it's getting stronger, I don't know what to do
Correct behavior: call create_booking with customer_issue="Caller smells a strengthening gas \
odor near their furnace.", job_type="gas leak", urgency="emergency", suggested_action="Instruct \
caller to leave the house and dispatch a technician immediately." No other text is needed.

--- Example 2: routine, enough info to book ---
Relevant company info:
- All repairs and installations are backed by a 1-year labor warranty in addition to the \
manufacturer's parts warranty.

Caller: My kitchen faucet has had a slow drip for about a week, I'd like to get it fixed
Correct behavior: call create_booking with customer_issue="Caller has a slow-dripping kitchen \
faucet that has persisted for about a week.", job_type="faucet repair", urgency="low", \
suggested_action="Schedule next available appointment."

--- Example 3: ambiguous, requires a follow-up question ---
Relevant company info:
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: uh yeah hi, something's wrong with my thing outside, the box, I don't know, it's making a noise
Correct output (plain text, no tool call):
What kind of outdoor unit is it — an AC/HVAC condenser, an electrical panel, or something else — and what kind of noise is it making?

--- Example 4: factual question, still needs a clarifying question ---
Relevant company info:
- Our regular business hours are Monday through Friday, 8:00 AM to 6:00 PM, and Saturday 9:00 \
AM to 2:00 PM.
- We offer 24/7 emergency HVAC service for no-heat and no-cool situations, with a 2-hour \
average response time.

Caller: Are you open right now? Also my heater just stopped working.
Correct output (plain text, no tool call):
We're open Monday through Friday 8am-6pm and Saturday 9am-2pm, but we also run 24/7 emergency service for no-heat situations. Is the heater completely out, and how cold is it inside your home right now?
"""


def retrieve_relevant_facts(voyage_client, collection, query):
    query_embedding = voyage_client.embed(
        [query], model=EMBED_MODEL, input_type="query"
    ).embeddings[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=N_RESULTS)
    return results["documents"][0]


def build_user_message(caller_message, facts):
    facts_block = "\n".join(f"- {fact}" for fact in facts)
    return f"Relevant company info:\n{facts_block}\n\nCaller: {caller_message}"


def get_reply(client, history):
    return client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        tools=[CREATE_BOOKING_TOOL],
        messages=history,
    )


def create_booking(details):
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = (
        f"{timestamp} | job_type={details.get('job_type')} | "
        f"urgency={details.get('urgency')} | "
        f"customer_issue={details.get('customer_issue')} | "
        f"suggested_action={details.get('suggested_action')}\n"
    )
    with open(BOOKINGS_LOG_PATH, "a") as f:
        f.write(line)
    print(f"Booking created: {details.get('job_type')} - {details.get('urgency')}")


def main():
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    client = Anthropic()
    history = []

    caller_input = input("Caller: ")
    facts = retrieve_relevant_facts(voyage_client, collection, caller_input)
    history.append({"role": "user", "content": build_user_message(caller_input, facts)})

    for exchange in range(MAX_EXCHANGES):
        response = get_reply(client, history)
        history.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"Dispatcher: {block.text.strip()}")

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        booking_call = next((b for b in tool_calls if b.name == "create_booking"), None)

        if booking_call is not None:
            create_booking(booking_call.input)
            return

        if not tool_calls and not any(b.type == "text" for b in response.content):
            print("Something went wrong — the dispatcher's response had no text or tool call.")

        caller_input = input("Caller: ")
        facts = retrieve_relevant_facts(voyage_client, collection, caller_input)
        history.append({"role": "user", "content": build_user_message(caller_input, facts)})

    print("Reached maximum exchanges without a booking.")
    sys.exit(1)


if __name__ == "__main__":
    main()
