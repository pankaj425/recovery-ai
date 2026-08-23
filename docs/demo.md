# Demo Playbook

Prep (once):
```bash
cd backend && python scripts/seed_database.py      # ~20k transactions, ~33k attempts
cd ../frontend && npm install
# Terminal A: cd backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000
# Terminal B: cd frontend && npm run dev
```

Login at http://localhost:5173 — `merchant@recovery.ai` / `demo1234`.

## 5-minute walkthrough

### 1 · Overview (30s)
Point out **Revenue at Risk** (~₹69L), **Potentially Recoverable** (~₹33L),
failure rate ~21%, and the live trend charts. Everything is computed from the
seeded database — refresh and simulate to watch it move.

### 2 · Revenue Recovery pipeline (90s)
Sorted by expected ₹, not just probability. Open the top CRITICAL row:
**Rahul Sharma, ₹50,000, fraud_suspected** — flagged by the risk engine but he's
a loyal customer with 10+ successful transactions. The AI flags it as a likely
false positive, escalates to CRITICAL for human review instead of auto-retrying.
Show the **score breakdown bars**: each component of the 88/100 score is visible.
Approve → Execute the MANUAL_RISK_REVIEW action.

### 3 · Live webhook simulation (60s)
```bash
cd backend/scripts && python simulate_webhooks.py --url http://localhost:8000 --count 25
```
Refresh Overview — new failures ingested, new opportunities scored automatically.
Mention: HMAC signature verification, idempotency on event_id, async queue mode.

### 4 · AI Assistant (90s)
Ask:
- *"How much revenue can we potentially recover?"* → grounded summary with metric chips.
- *"Show me all failed transactions for cus_amit01"* → customer drill-down via tool call.
- *"Which payment method loses us the most money?"* → method analytics.

Highlight `tools_used` badges: the agent answers from real queries, never invents numbers,
and runs fully offline with the mock provider.

### 5 · Analytics — the money slide (60s)
Baseline vs RecoveryAI on identical data:
recovery rate **~18% → ~53%**, recovered revenue **~₹5.9L → ~₹16.9L** on the
100-opportunity cohort (**+186%**, ~2.9× improvement multiple),
plus ~32 wasted retries avoided. CLI proof:
```bash
python scripts/run_demo.py    # prints the same comparison from the live DB
```

### 6 · Close (30s)
- Interpretable ML — every score explainable, every decision audited (`ai_decisions`, `score_audit`).
- Human-in-the-loop approval gates; fraud cases escalate, never auto-retry.
- Production-shaped: JWT auth, rate limiting, uniform error envelopes,
  Docker Compose with Postgres, 33 green tests.

## Judge Q&A ammo

- **"Is the ML real?"** — Yes: logistic regression trained on labeled outcomes
  (seeded ground truth), versioned artifact, feature contributions stored per decision.
- **"Where do the baseline numbers come from?"** — `analytics/baseline.py`: rule-based
  dunning policy evaluated on the same cohort; assumptions documented in settings.
- **"Does it work without internet?"** — Entirely; mock LLM provider + SQLite.
- **"Scale?"** — Seed runs 33k attempts in ~19s; API paged endpoints are indexed;
  Postgres-ready via one env var.
