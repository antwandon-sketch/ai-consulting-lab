import json
import os
import sys

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

MAX_EXCHANGES = 4

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
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    client = Anthropic()
    history = []

    caller_input = input("Caller: ")
    facts = retrieve_relevant_facts(voyage_client, collection, caller_input)
    history.append({"role": "user", "content": build_user_message(caller_input, facts)})

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
        facts = retrieve_relevant_facts(voyage_client, collection, caller_input)
        history.append({"role": "user", "content": build_user_message(caller_input, facts)})

    print("Reached maximum exchanges without a confident qualification.")
    print("Raw last reply:")
    print(raw_text)
    sys.exit(1)


if __name__ == "__main__":
    main()
