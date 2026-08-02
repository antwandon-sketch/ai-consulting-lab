
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

## 2026-07-29 (continued) — Payments Migrated to Neon Too

- Found the same ephemeral-storage bug in the Stripe webhook route:
  payments.log was being written to Render's local disk, same failure mode
  as bookings.log before tonight's fix — caught this by auditing for the
  pattern elsewhere in app.py rather than assuming one fix covered it.
- Added a payments table to Neon (via db.py's init_db) and a save_payment()
  function. Built with ON CONFLICT DO NOTHING on session_id specifically
  because Stripe retries webhook delivery — this makes repeated webhook
  deliveries for the same payment a no-op instead of creating duplicates.
- Patched app.py's /webhook route to call save_payment() instead of writing
  to payments.log.
- Verified live with Stripe CLI (stripe listen + stripe trigger
  checkout.session.completed): multiple webhook deliveries came through
  (200 on each), but list_payments() correctly shows exactly one row —
  proving the idempotency logic works under real repeated-delivery
  conditions, not just in theory.
- Pushed and deployed to Render — bookings and payments are now both
  persistent, validated, and handled consistently across the codebase.

**Next up:** more voice-call reliability testing (paused for tonight — house
is quiet, son's asleep), and still waiting on Retell KYC verification for the
real phone number.

## 2026-07-30 — Repo Polish + Full Credential Rotation

**Repo restructure for code quality/portfolio readiness:**
- Split `app.py` into blueprints: `routes/dispatch.py` (qualify + booking),
  `routes/billing.py` (Stripe), with `config.py` centralizing env vars and
  shared clients. `app.py` is now a slim entry point.
- Fixed a real bug found in the process: `create_checkout_session` had
  hardcoded `http://127.0.0.1:5001` redirect URLs — would have sent real
  customers to an unreachable localhost address in production. Now driven
  by a `BASE_URL` env var.
- Added a pytest suite (33 tests, `tests/`) covering `/book` validation,
  including regression coverage for the `"UNKNOWN"` placeholder incident
  from this morning. Used the suite to safely verify the blueprint
  restructure didn't break anything — all 33 passed before and after.
- Removed `__pycache__` from git tracking (was accidentally committed
  despite being in `.gitignore`'s intent).
- Added a public-facing `README.md` — architecture (with a Mermaid diagram,
  renders natively on GitHub), tech stack, API reference, setup
  instructions, and testing notes.

**Credential exposure and full rotation:**
- While drafting the README's example `.env` section, real secret values
  got manually typed in instead of the placeholder text — these were then
  visible in a screenshot shared in chat. Separately, a real Neon
  connection string (with password) got pasted directly into chat text
  during troubleshooting.
- Confirmed via `git status` that `README.md` had never been committed, so
  the exposure never reached GitHub — but treated all values as compromised
  regardless, since they'd been visible on-screen either way.
- Rotated all four credentials: `APP_SECRET_KEY`, `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`, `DATABASE_URL` (Neon password reset — twice,
  since the first new connection string also got exposed in chat before
  being finalized).
- Discovered along the way: there was no permanent Stripe webhook
  destination pointing at production — only a local CLI listener used for
  testing. Created a real destination (`havoc-qualifier-api production`)
  pointed at `https://havoc-qualifier-api.onrender.com/webhook`, subscribed
  to `checkout.session.completed` — this was a real gap, not just a
  rotation side-effect.
- Hit several real snags during rotation, each traced to ground truth rather
  than guessed at: a `.env` line that ended up blank because a Python
  `input()` one-liner's prompt text got merged with the actual value during
  paste; `stripe listen --forward-to` generating its own temporary signing
  secret separate from the real destination's secret, causing confusing
  400s that had nothing to do with the rotation itself; and one `.env` line
  that ended up containing a literal terminal command (`cd
  ~/ai-consulting-lab`) instead of the actual key value, from a copy-paste
  mixup.
- Final state, fully verified: local `pytest` suite still 33/33, a real
  production booking succeeded end-to-end with the new `APP_SECRET_KEY`
  (booking id 11), and a real Stripe-triggered webhook returned 200 with the
  new signing secret and new database password.

**Lesson for next time:** avoid interactive Python `input()` one-liners for
pasting secrets into `.env` — they're fragile in a way that fails silently
(blank value saved, no error). Prefer either a direct heredoc/python script
with the value already embedded, or a plain manual edit in `nano`.

**Next up:** push the now-fixed `README.md` (see below), then continue
outreach — Batch 2 still queued, 8 prospects not yet batched.

## 2026-07-30 (evening) — Credential rotation broke live bookings

- All 4 test calls between 3:03-3:08 PM today failed silently (agent said it booked
  the appointment, but `create_booking` was actually returning HTTP 401:
  "Missing or invalid X-API-Key header").
- Root cause: the full credential rotation done earlier today updated `APP_SECRET_KEY`
  on Render, but Retell's `create_booking` custom function still had the OLD value
  hardcoded into its X-API-Key header field. Render and Retell don't share env vars
  automatically — this header has to be manually updated in Retell any time
  APP_SECRET_KEY rotates.
- Fixed by copying the current APP_SECRET_KEY value from Render's Environment tab
  into the X-API-Key header field on the create_booking function in Retell's agent
  config. Re-tested at 3:43 PM - call succeeded.
- Lesson: any future credential rotation must include a check of Retell's custom
  function headers, not just Render's env vars, or bookings will fail silently
  (agent still says "you're all set" even when the backend call actually failed).
- Also noticed: noticeable pause after the agent said "let me get that booked" before
  confirming - likely Render free tier cold start on the /book endpoint. Investigating
  actual latency via Retell API call data.

## 2026-08-01 — ANTHROPIC_API_KEY exposure and rotation

- The `ANTHROPIC_API_KEY` value was exposed in a chat session with another agent
  thread tonight. This is separate from the 2026-07-30 four-credential rotation
  (`APP_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `DATABASE_URL`)
  documented above — that rotation did not include `ANTHROPIC_API_KEY`.
- Rotated the key and updated `.env` in this project folder. Confirmed: only one
  `ANTHROPIC_API_KEY` line present (no duplicates), and the new key authenticates
  successfully against the Anthropic API.
- The exposed key was never committed to the repo at any point — confirmed via
  `git log --all --full-history -- .env`, which returns nothing across all of
  history. `.env` has never been tracked by git.
