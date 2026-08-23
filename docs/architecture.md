# Architecture

## High-level flow

```
Payment gateway ──webhook──▶ Ingestion API ──▶ Root Cause Classifier
                                   │                    │
                            (idempotent,          Failure Code + Reason
                             async queue)               │
                                   │                    ▼
                                   ▼            Recovery Probability Model
                              Transaction            (interpretable ML)
                              /Attempts                    │
                                   │                       ▼
                                   └────────▶ Scoring & Prioritization Engine
                                                    │
                                              Expected ₹ = P(recover) × amount × uplift
                                                    │
                          ┌─────────────────────────┼──────────────────────┐
                          ▼                         ▼                      ▼
                   Dashboard UI             Action Workflow           AI Assistant
                   (React/Recharts)      (recommend → approve →   (tool-calling agent
                                          execute, simulated)      over DB tools)
```

## Backend layout (`backend/app/`)

| Package        | Responsibility |
|----------------|----------------|
| `core/`        | Settings (env-driven), security (JWT/PBKDF2), exceptions → uniform error envelope, logging |
| `models/`      | SQLAlchemy 2 entities: User/Customer, Transaction/PaymentAttempt, RecoveryOpportunity/RecoveryAction/AIDecision, WebhookEvent |
| `schemas/`     | Pydantic v2 request/response contracts; paged envelope `{items, meta}` |
| `repositories/`| Query layer — filtering, sorting, pagination kept out of services |
| `services/`    | Business core: failure classification, scoring, retry engine, recommendations, opportunity pipeline, webhook processing, auth |
| `ml/`          | Feature builder + pure-Python logistic regression + versioned model registry with audit trail |
| `analytics/`   | SQL aggregations for dashboard metrics + baseline-vs-AI counterfactual engine |
| `agents/`      | Tool registry, intent classifier, LLM providers (OpenAI/Groq/Mock), orchestrator that composes deterministic answers from tool output |
| `api/v1/`      | 21 routes under `/api/v1`: auth, webhooks, recovery, commerce, analytics, ai |
| `workers/`     | Background webhook queue worker |

## Key design decisions

1. **Observed facts vs model estimates.** Every analytics number is either an
   SQL aggregate (facts: revenue at risk, failure rate) or clearly prefixed
   (`potential_`, `estimated_`, `expected_`) as a model-derived projection.
2. **Explainability first.** Each opportunity persists its score breakdown
   (6 weighted components), the model's feature contributions, and a plain-English
   summary — the UI renders them directly. No black boxes.
3. **Deterministic AI.** The agent's numbers always come from database tools;
   the LLM only shapes narrative. With `LLM_PROVIDER=mock` the whole product runs
   offline and reproducibly.
4. **Human-in-the-loop.** Customer-affecting actions require explicit approval;
   fraud-flagged high-value cases escalate to CRITICAL for manual review instead
   of blind retries.
5. **Idempotent ingestion.** Unique `event_id` on `webhook_events`; replays are
   safely ignored; attempt-number gaps are backfilled so attempt-count features
   stay truthful.
6. **Zero-config dev, production-shaped.** SQLite by default, PostgreSQL via one
   env var; same code path in Docker Compose.

## Scoring model

Score = Σ weights × normalized components:

| Component          | Weight | Normalization |
|--------------------|-------:|---------------|
| Transaction value  | 25     | log10(amount+1)/log10(60,001) |
| Failure frequency  | 10     | attempts/4 capped |
| Customer value     | 20     | LTV/₹120k capped |
| Historical success | 10     | past recovery successes |
| AI probability     | 25     | raw model output |
| Recency            | 10     | 0.5 + 0.5·e^(−hours/72) |

Priority bands: ≥85 CRITICAL · ≥70 HIGH · ≥55 MEDIUM · else LOW.
Business-rule escalation can force CRITICAL (e.g. FRAUD_OR_RISK ∧ amount ≥ ₹50k ∧ loyal customer).

## Baseline comparison methodology

- **Baseline:** rule-based dunning — retry every failed payment once after 24h,
  success probability fixed per root cause (12–30%), no prioritization.
- **AI-assisted:** pursue only opportunities above the expected-value threshold,
  using predicted probability × amount ranking; skip hopeless low-value ones.
- Both are evaluated over the same transaction set (`analytics/baseline.py`),
  reported as rates, rupees, improvement multiple and avoided wasted retries.
