# RecoveryAI — Revenue Recovery Intelligence Platform

Turn failed payments into recovered revenue. RecoveryAI ingests payment-failure
webhooks, classifies the root cause, predicts recovery probability with an
interpretable ML model, ranks every failure by expected recovery value, and gives
merchants an explainable action queue plus a tool-calling AI assistant.

**The headline:** rule-based dunning recovers ~18% of at-risk revenue.
RecoveryAI recovers **~53%** on the same book — verified live against the seeded
database (`scripts/run_demo.py`).

## Stack

| Layer     | Tech |
|-----------|------|
| Backend   | FastAPI + SQLAlchemy 2 + Pydantic v2, JWT auth |
| Database  | SQLite (zero-config dev) or PostgreSQL via `DATABASE_URL` |
| ML        | Pure-Python logistic regression (no numpy/sklearn), deterministic seed |
| AI agent  | Tool-calling orchestrator — OpenAI / Groq / offline Mock provider |
| Frontend  | React 18 + Vite + Tailwind CSS + Recharts |
| Ops       | Docker Compose (Postgres + API + nginx frontend) |

## Quick start (local, no Docker)

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate        # Windows; source .venv/bin/activate on unix
pip install -r requirements.txt
copy .env.example .env                                # defaults work out of the box

python scripts/seed_database.py                       # synthetic dataset: ~5k customers, ~20k txns, ~33k attempts
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# 2. Frontend (new terminal)
cd ../frontend
npm install
npm run dev                                           # http://localhost:5173
```

Login: **merchant@recovery.ai / demo1234**

### With Docker

```bash
docker compose up --build
# dashboard: http://localhost:8080 · API docs: http://localhost:8000/docs
```

Then seed once inside the container:
```bash
docker compose exec api python scripts/seed_database.py
```

## What's inside

- **Webhook ingestion** — `POST /api/v1/webhook/payment-failed`, HMAC-SHA256
  signature verification, idempotent on `event_id`, async queue mode (`?sync=false`).
- **Root cause classification** — failure code + reason → one of 5 causes
  (payment method issue / bank-network / fraud-risk / customer behavior / system).
- **Recovery probability** — interpretable logistic model over amount band,
  attempt count, customer tenure/LTV/history, method, recency; versioned artifact
  with audit trail per decision.
- **Deterministic scoring** — weighted 0–100 score (value, frequency, LTV,
  historical success, probability, recency) with business-rule escalation
  (e.g. ₹50k+ fraud-flag on a loyal customer → CRITICAL for human review).
- **Expected recovery value** — probability × amount × root-cause uplift;
  pipeline sorted by rupees you can actually win back.
- **Action workflow** — recommended retry policy per cause; human approval gate
  before execution; executions simulated against the retry engine's success model.
- **Analytics & counterfactual** — live KPIs, trends, method/failure analytics and
  a baseline-vs-AI comparison proving the improvement multiple (~2.9×).
- **AI assistant** — natural-language questions answered from real database tools
  (revenue summary, top opportunities, customer analysis, failure breakdown,
  payment methods); works fully offline with the mock provider.

## Demo script (5 minutes)

1. Login → Overview: revenue at risk, recoverable value, trends.
2. Revenue Recovery: pipeline sorted by expected ₹ — open the CRITICAL row
   (Rahul Sharma, ₹50k, fraud false-positive): see score breakdown, approve +
   execute manual review.
3. Simulate live failures:
   `backend/scripts/simulate_webhooks.py --url http://localhost:8000 --count 25`
   → refresh Overview, watch numbers move.
4. AI Assistant: "How much revenue can we potentially recover?" then
   "Show me all failed transactions for cus_amit01".
5. Analytics: baseline vs RecoveryAI bars — the money slide.

Full walkthrough: [`docs/demo.md`](docs/demo.md)

## Documentation

- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [AI agent design](docs/ai-agent.md)
- [Demo playbook](docs/demo.md)

## Testing

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests -q   # 33 tests
```

Covers webhook idempotency/signature/validation, scoring bands, root-cause
classification, retry policies, ML determinism/bounds, agent tools & chat,
analytics aggregation, auth gating, error envelopes.

## Configuration

All settings are environment-driven (see `backend/.env.example`):
`DATABASE_URL`, `SECRET_KEY`, `WEBHOOK_SECRET`,
`ALLOW_UNSIGNED_WEBHOOKS`, `LLM_PROVIDER` (`mock|openai|groq`),
`OPENAI_API_KEY` / `GROQ_API_KEY`.

> Demo build: all recovery actions are **simulated** — no real emails, SMS, or gateway calls.
