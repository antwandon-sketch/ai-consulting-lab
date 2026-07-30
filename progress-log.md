
## 2026-07-27 — RAG Basics (Week 5 start)

- What I built:
  - Signed up for Voyage AI, added VOYAGE_API_KEY to .env
  - company_docs.py — sample HVAC company facts (hours, pricing, service area, emergency policy)
  - ingest.py — embeds facts with Voyage AI, stores them in a local Chroma vector database
  - search.py — takes a question, embeds it, retrieves the most relevant stored facts

- What broke:
  - Terminal window closed mid-edit before .env update saved — fixed by using
    echo "..." >> .env instead of a text editor, so nothing stays open to lose

- What I learned:
  - Anthropic doesn't make its own embedding model — Voyage AI is the standard pairing
  - Embeddings match on meaning, not keywords — "emergencies at night" correctly pulled
    the "24/7 emergency service" fact despite sharing no words
  - Good RAG surfaces the closest real facts instead of inventing an answer when the
    exact thing isn't in the data

- Next step:
  - Wire search.py's retrieval into the call qualifier

---

## 2026-07-28 — Agents, Sub-Agents, MCP, Deployment, and Billing (Weeks 7-11)

- What I built:
  - qualify_and_book.py — added real tool use (Anthropic function calling); qualified
    calls now trigger an actual create_booking tool call, logged to bookings.log
  - agent_orchestrator.py — split the single agent into three narrow sub-agents
    (qualifier, scheduler, notifier) coordinated by an orchestrator; logs to
    bookings.log and sms.log
  - Connected Claude Code to an external MCP server (claude-code-docs) and verified a
    labeled tool call
  - mcp_server.py — built and ran my own custom MCP server (FastMCP) exposing
    check_service_area, get_business_hours, get_pricing_estimate; connected Claude Code
    to it as a client and confirmed real tool calls ("Called hvac-tools")
  - app.py — wrapped the qualifier as a real Flask API (POST /qualify), added an
    X-API-Key header check for basic protection
  - Pushed the whole project to GitHub (private repo), cleaned up stray test files and
    excluded the virtual environment via .gitignore
  - Deployed app.py live on Render — first real public URL
    (https://havoc-qualifier-api.onrender.com), tested successfully with a live curl
    request
  - Added Stripe billing in test mode: /pricing page, /create-checkout-session,
    /success, /cancel — completed a full test checkout with Stripe's test card

- What broke:
  - Had to set up a Python 3.12 virtual environment (mcp-env) since MCP's SDK requires
    3.10+ and the system Python was 3.9.6
  - claude mcp add failed first with a literal placeholder path instead of the real
    Python path — fixed by using the actual `which python` output
  - Local port 5000 was occupied by macOS AirPlay Receiver — switched Flask to port 5001
    for local testing (not an issue in production, since hosting platforms assign PORT)
  - GitHub Desktop published an empty repo by mistake — redid the push from the
    terminal instead
  - Accidentally committed the entire mcp-env virtual environment (thousands of files)
    to git before catching it — removed it with git rm -r --cached and added it to
    .gitignore
  - GitHub rejected password auth — had to generate a Personal Access Token instead
  - Stripe key wasn't loading because .env had it with no variable name prefix —
    Claude Code caught and fixed this

- What I learned:
  - The difference between a tool built inline (create_booking) versus a tool served
    over MCP (hvac-tools) — same concept, different reach: MCP tools are callable by
    any MCP client, not just my own script
  - Why sub-agents matter: narrow scope means each piece is independently testable, and
    a notification agent that never sees raw emergency details can't accidentally
    fabricate unsafe language
  - Virtual environments isolate dependencies/Python versions per project without
    breaking other scripts
  - Why .env must never be committed to git, and why virtual environments shouldn't be
    either — both should be rebuilt/configured per machine, not shipped as files
  - Render's free tier spins down after inactivity (fine for demos, not for real
    production traffic)
  - The core Stripe Checkout pattern: create a Checkout Session server-side, redirect
    the customer to Stripe's hosted page, handle success/cancel redirects

- Next step:
  - Add a Stripe webhook so payment confirmation comes from Stripe directly instead of
    just trusting the /success redirect
  - Week 12: package this build into a case study/demo for outreach

## 2026-07-29 — Outreach Prep: Batches 1 & 2

- Drafted 3 outreach email variants (Lost Revenue / Time-Relief / Competitor Edge hooks),
  all closing with a direct "reply YES" CTA. Signature format locked: Name / All Rhodes
  Media / phone / email.
- Picked Batch 1 (6 businesses) and Batch 2 (6 businesses) from the verified 20-business
  prospect list, rotating hook variants across each batch.
- Verified real contact emails for 11 of 12 businesses directly on their own sites/FB
  pages (not from third-party data brokers). Lantz Home Services has no public email —
  contact form or phone only.
- Airco and SALT (both large multi-trade shops) also had no public email — moved to a
  phone-only outreach list alongside Lantz for Friday's calls.
- Fully drafted, ready-to-send versions of all 12 emails (no placeholders).
- Plan: send Batch 1 this afternoon (2026-07-29), follow up with phone calls Friday
  (2026-07-31), targeting late morning before contractors are off-site for the weekend.

**Next up:** send Batch 1, track replies, call Friday, then move to Batch 2 send.

## 2026-07-29 (late session) — Persistent Storage + New Booking Fields

- Root-caused why bookings.log kept losing data: Render's free tier wipes local
  disk on every restart — not a bug in the log-writing code itself, the ground
  it sat on kept getting reset.
- Migrated booking storage to Neon (free serverless Postgres) — chosen over
  Supabase specifically because Neon's scale-to-zero resumes instantly, while
  Supabase free projects fully pause after a week of inactivity.
- Built db.py (init_db, save_booking, list_bookings) and wired it into app.py's
  /book route, replacing the file-append entirely.
- Added three new required fields end-to-end: customer_name, service_address,
  business_name — updated Retell's create_booking function schema, added
  descriptions, added a prompt instruction requiring the agent to collect name
  and address before booking (business_name is a fixed per-agent value, not
  asked of the caller).
- Caught and fixed a real validation gap: "required" in Retell's schema only
  forces a field to be present, not truthful — the backend was checking key
  presence, not blank values, so a rushed model could've saved an empty name
  silently. Hardened /book to reject blank/whitespace values the same as
  missing ones. Verified with two live curl tests (real data succeeds, blank
  customer_name correctly rejected with a 400).
- Verified the full loop live end-to-end via Retell Test Audio: agent asked
  for name + address, called create_booking, booking landed in Neon with all
  fields populated correctly (booking id 5).
- Discussed multi-business/multi-trade architecture: one Retell agent + one
  codebase can serve every client and trade type via dynamic variables and an
  inbound webhook (per-number lookup), rather than a separate agent per
  business. Deliberately NOT building the inbound webhook/multi-tenant lookup
  yet — no second client to justify it. business_name is hardcoded to a
  placeholder for now.

**Next up:** more test calls to confirm the agent reliably asks for
name/address every time (one clean pass isn't enough data yet), then revisit
Retell KYC status for the real phone number.
