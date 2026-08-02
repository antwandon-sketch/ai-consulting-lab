# All Rhodes Media — AI Systems

**Master context doc.** Keep this current. Upload to the Claude Project files so any new
thread starts with full context.

Last updated: 2026-07-29

---

## The Business

**Operator:** Anthony Letson · All Rhodes Media · Georgetown, TX
**Contact:** 512-945-2249 · allrhodesmedia@gmail.com
**Working hours:** Evenings/nights and weekends (full-time day job)

**Niche:** Texas high-ticket home services — HVAC, plumbing, electrical, roofing.
Georgetown / Williamson County / Austin metro first.

**Core offer:** 24/7 AI voice agent that answers missed and after-hours calls, qualifies
the job, books it, and sends SMS confirmation.

**Pricing:** $2,000–$8,000 setup + $300–$900/month per location.
Voice cost basis: ~$0.11–$0.15/min all-in (Retell + LLM + telephony). At 200 min/month
that's ~$26 cost against the retainer.

**90-day goal:** First paying client + a repeatable pitch.

**Planned upsell modules** (same clients, stacked retainers): estimate follow-up, review
automation, lead reactivation, dispatch.

**Sales asset:** `missed-call-recovery-one-pager.pdf`/`.md` — one page, branded with the
All Rhodes Media logo, ready to send. Offers a free custom demo before any payment.

---

## Live Systems — STATUS: PRODUCT IS FUNCTIONALLY COMPLETE

| Thing | Where | Status |
|---|---|---|
| Qualifier/booking API | `https://havoc-qualifier-api.onrender.com` | Live (Render free tier) |
| Voice agent | Retell — "Single-Prompt Agent" | **Fully working end-to-end** — reasons, qualifies, books via real API call, confirms by voice. Verified live. No phone number yet (KYC pending). |
| Repo | `github.com/antwandon-sketch/ai-consulting-lab` (private) | Active, reorganized into folders |
| Billing | Stripe (test mode) | Checkout + webhook fully working, signature-verified |

**Endpoints on the API:**
- `GET /` — health check
- `POST /qualify` — text transcript in, structured qualification out (needs `X-API-Key`)
- `POST /book` — logs a booking (needs `X-API-Key`) — **this is what the live Retell voice
  agent calls** via its `create_booking` custom function
- `POST /webhook` — Stripe payment confirmation, signature-verified, tested via Stripe CLI
- `GET /pricing`, `POST /create-checkout-session`, `/success`, `/cancel` — Stripe Checkout

**Verified end-to-end voice flow (tested live via Retell's Test Audio):** Caller describes
issue → agent asks clarifying questions if needed → agent determines job_type/urgency/
is_emergency → agent calls `create_booking` function → real POST to `/book` on Render →
booking logged → agent confirms verbally to caller, including safety instructions for
true emergencies (e.g. shutting off water/gas). This is the actual product.

---

## CURRENT BLOCKER

**Retell KYC (Know Your Customer) verification failed**, needs manual review from
Retell support (`support@retellai.com`). This blocks buying a real phone number — without
it, the agent only works via browser-based Test Audio, not real phone calls. Anthony has
been in contact with Retell support; resolution pending as of 2026-07-29.

**Once resolved:** buy a local (512/737) number in Retell → Phone Numbers → attach it to
the Single-Prompt Agent → call it from a real cell phone → record the first real demo call.

---

## Stack

- **Language/runtime:** Python 3.12 (venv `mcp-env`), Flask + gunicorn
- **LLM:** Anthropic API, `claude-sonnet-5` (note: Sonnet 5 removed `temperature`/`top_p`/
  `top_k` — use `output_config={"effort": "low"}` instead)
- **Embeddings:** Voyage AI (`voyage-3.5`) — Anthropic has no first-party embedding model
- **Vector DB:** Chroma (local)
- **Voice:** Retell AI, ElevenLabs voice ("Andrew"), GPT 5.1 as the in-call model
- **Hosting:** Render (free tier — spins down after inactivity, ~50s cold start)
- **Payments:** Stripe + Stripe CLI for local webhook testing
- **MCP:** FastMCP (`mcp/mcp_server.py` — `hvac-tools` server, exposes
  `check_service_area`, `get_business_hours`, `get_pricing_estimate`)

---

## Repo Structure (reorganized 2026-07-29)

```
ai-consulting-lab/
├── PROJECT.md              ← this file
├── progress-log.md         ← session-by-session log
├── app.py                  ← the deployed Flask service — DO NOT MOVE, Render depends on this path
├── requirements.txt        ← DO NOT MOVE, same reason
├── agents/
│   └── hvac-dispatch/      ← qualify_call*.py, company_docs.py, ingest.py, search.py,
│                              qualify_and_book.py, agent_orchestrator.py
├── mcp/                    ← mcp_server.py
└── archive/                ← early learning scripts (ask.py etc.)
```

---

## Curriculum Position

14-week roadmap (`ai-consulting-roadmap.md`). **Complete: Weeks 1–12 plus the full voice
layer (originally slated for later weeks) — done ahead of schedule.**
Remaining: Weeks 13–14 — outreach, first client.

**Immediate next steps:**
1. Resolve Retell KYC → attach real phone number → record a real demo call
2. Begin outreach using the verified prospect list (below) and the one-pager
3. Land first paying client (90-day target)

---

## Verified Prospect List (Georgetown/Williamson County) — 20 businesses

Built via Google Places verification (not raw Perplexity output — see note below).
Every phone number and rating below was independently confirmed.

**Georgetown:** GTX Plumbing (512-688-7442, 4.8★), Walker Plumbing Co (512-863-0469,
4.9★), Lee Whiteaker Plumbing (512-869-4828, 4.9★), Neal HVAC (512-248-2665, 4.9★/954
reviews), Cox Electric (512-876-8766, 4.8★), Norrell Electric (512-863-0143, 5.0★), Ark
Roofer (512-948-1638, 4.9★/506 reviews)

**Round Rock:** Airco AC/Electrical/Plumbing (512-537-1234, 4.8★/1,039 reviews), JC
Electrical Services (512-800-4117, 4.9★), Mustang Plumbing (512-733-1110, 3.4★ — lower
priority)

**Cedar Park:** Proven Plumbing & Air (512-775-1234, 4.9★/3,051 reviews), JustUs Plumbing
(512-503-1098, 4.9★/846 reviews), A&T Service Plumbing (512-825-0983, 4.6★), SALT
Plumbing Air & Electric (512-861-8874, 4.9★/351 reviews), Heritage Roofing & Construction
(512-528-5559, 4.6★/567 reviews)

**Leander:** Prodigy Heating & Air (512-778-5247, 5.0★/477 reviews), MLD HVAC
(512-528-4258, 4.9★), Bear Electric (512-698-2404, 5.0★/387 reviews), Cedar Park Plumbing
(512-260-5079, 4.9★)

**Liberty Hill / Lago Vista:** Lantz Home Services (512-710-1032, 4.9★/1,334 reviews)

**Explicitly excluded/dropped, do not contact:**
- Stryker Heating and Cooling (Cedar Park) — real business, but genuinely bad reputation
  (lawsuits, $18K+ dispute, called "a MIRAGE" by a reviewer)
- Legacy Roofing Pros (Round Rock) — active fraud allegation in reviews ("owner took my
  money and vanished... legal action")
- Plumb & Order, Caden Roofing — dropped per Anthony's preference (Caden is Austin-based,
  not truly local)

---

## Outreach Templates

Three email variants drafted (direct/casual/short). See conversation history for full
text, or ask Claude to regenerate. Key principle: **no claims about a specific business's
complaints or reviews** — ask a general question ("do missed calls cost you jobs?") rather
than asserting a specific fact, since AI research tools can fabricate plausible-sounding
review quotes that don't actually exist (see lesson below).

---

## Conventions and Hard-Won Lessons

- **`.env` is local only.** Render needs the same variables added manually in its
  Environment tab. A missing one crashes the deploy on boot (this happened with
  `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` — added locally but forgotten on Render,
  causing a production crash days later). Same will be true of any new host.
- **Never commit** `.env`, `mcp-env/`, `__pycache__/`, `.DS_Store`.
- **Header name vs. variable name:** the API checks for a header literally named
  `X-API-Key`. The local variable holding its value is `APP_SECRET_KEY`. Not the same
  thing.
- **Port 5000 is taken by macOS AirPlay.** Local dev runs on 5001 (`PORT=5001` in `.env`).
- **Retell function parameter names must exactly match the API's expected fields.**
  A single-character typo (`is_emergecy`) causes a silent 400 with a misleading
  "missing required field" error. Check the raw tool-call payload in Call History →
  Detail Logs when debugging — this is exactly how the real bug was found and fixed.
- **Retell's "Payload: args only" toggle** controls whether custom function calls send a
  flat argument object vs. a nested structure. Turn it on for simple REST endpoints.
- **Turn on "Talk While Waiting"** for any Retell function that hits the Render API —
  cold starts can take ~50s and silence kills calls.
- **Models can't reliably self-report their name.** Verify from the API response's
  `model` field, not by asking.
- **Free-tier Render has no persistent filesystem** — `bookings.log` resets on restart.
  A real client needs a database.
- **GitHub no longer accepts password auth for git operations** — use a Personal Access
  Token instead (Settings → Developer settings → Personal access tokens).
- **AI research tools (Perplexity, etc.) can fabricate plausible-sounding but false
  content** — a "sourced" customer review quote used to justify a lead turned out not to
  exist anywhere in that business's actual reviews. Always independently verify specific
  factual claims (especially quotes) before using them in outreach. Business
  names/phone numbers are lower-risk to verify (via Google Places) than quoted text.
- **MCP's Python SDK needs Python 3.10+** — required setting up a separate `mcp-env`
  venv since system Python was 3.9.6.
- **A pushed fix isn't a deployed fix.** Confirmed the hard way: `git push` succeeded
  and GitHub had the correct code, but Render's auto-deploy silently didn't trigger,
  so production kept serving old code for a while (a fix meant to reject placeholder
  values like "UNKNOWN" kept accepting them in production, despite testing clean
  locally). After any push meant to fix something real, check Render's Logs tab for
  a fresh "Deploying..." entry before trusting it's live — if it's missing, use the
  Manual Deploy button rather than assuming the push alone was enough.

---

## Open Threads / Decisions Made

- **Brand:** AI work lives under All Rhodes Media, not a separate entity. Logo created
  (AR monogram, dark background) and added to the one-pager.
- **Email:** currently Gmail (`allrhodesmedia@gmail.com`), used for everything. Domain +
  dedicated email recommended before high-volume outreach, both for credibility and to
  protect the main account from cold-email deliverability risk. Not done yet.
- **Declined:** peptide-supplier automation (ASTRA) — grey-market regulatory exposure
  (RUO-labeled compounds sold with injection supplies, no institutional verification),
  and off-mission before first client.
- **Sales/outreach agent:** discussed as a future build (internal tool vs. productized
  "lead reactivation" module), deliberately paused — focus stayed on finishing and
  proving the core voice product first. Revisit after first client or once outreach
  is underway.
- **Obsidian:** tried, found confusing, paused. Using a plain `progress-log.md` in the
  repo instead — same content, no new tool to learn.

---

## Note for New Agent/Thread Sessions

When starting a new thread, say "read PROJECT.md" — it has full context on the product,
stack, blockers, and prospect list. When starting a new **agent** (e.g. the sales/outreach
agent, when that resumes), define up front:
1. **Who is it for** — the contractor's customers, or Anthony's own prospecting?
2. **Does it reuse the existing API** or need new endpoints?
3. **Where does it live** in the repo?
4. **Is it a sellable module** (goes in the upsell stack) or internal tooling?

## Session Wrap-Up Convention

At the end of each work session, Claude gives a 2-3 sentence "story" summary of
what was built or fixed — phrased so it can be repeated to an employer or
colleague, not just a technical changelog entry. Goal: build up a stack of
these over time as practice material for interviews and technical conversations,
and build comfort with industry terminology along the way.
