
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
