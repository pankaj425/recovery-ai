# API Reference

Base URL `/api/v1` · JSON only · Bearer JWT (`Authorization: Bearer <token>`).
Errors use a uniform envelope:

```json
{ "success": false, "error": { "code": "OPPORTUNITY_NOT_FOUND", "message": "…" } }
```

## Auth — `/auth`

| Method | Path     | Body / Params | Notes |
|--------|----------|---------------|-------|
| POST   | `/login` | `{email, password}` | → `{access_token, token_type, user}` |
| GET    | `/me`    | —             | Current user profile |

Demo credentials: `merchant@recovery.ai` / `demo1234`.

## Webhooks — `/webhook` (public, HMAC-verified)

### `POST /payment-failed`

Headers: `X-Signature: hex(HMAC-SHA256(raw_body, WEBHOOK_SIGNING_SECRET))`.
Dev convenience: `ALLOW_UNSIGNED_WEBHOOKS=true` skips verification.

Payload:
```json
{
  "event_id": "evt_unique_001",
  "transaction_id": "txn_100234",
  "customer_id": "cus_rahul01",
  "amount": 50000.0,
  "currency": "INR",
  "payment_method": "CARD",
  "payment_provider": "Razorpay",
  "status": "FAILED",                       // FAILED | ABANDONED
  "failure_code": "fraud_suspected",
  "failure_reason": "Flagged by risk engine",
  "attempt_number": 3,
  "metadata": { "device_fingerprint": "…" },
  "timestamp": "2025-06-01T10:00:00Z"
}
```

Query `?sync=false` defers processing to the background queue.
Responses: `202 accepted` (queued) · `200 processed` · duplicate `event_id`
returns idempotent success with `duplicate: true`; bad signature → `401`.

## Recovery — `/recovery`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/opportunities` | Paged pipeline. Filters: `priority`, `status`, `root_cause`, `search`; sort by `expected_recovery_value` (default), `recovery_score`, `revenue_at_risk`, `created_at`. Items include nested customer + transaction, probability, expected ₹, score, recommended action. |
| GET | `/opportunities/{id}` | Full detail + `explanation.score_breakdown`, model decisions, actions list |
| GET | `/status/{transaction_id}` | Failure diagnosis & recovery status for one transaction |
| POST | `/opportunities/{id}/actions` | Body `{action_type, channel?, approved?}` → creates action (approval gate) |
| POST | `/actions/{id}/approve` | Records approver, moves to approved state |
| POST | `/actions/{id}/execute` | Simulated execution against retry engine; stores result |

Action types: `UPDATE_PAYMENT_METHOD`, `DELAYED_RETRY`, `SMART_RETRY`,
`MANUAL_RISK_REVIEW`, `ABANDONED_CART_EMAIL`, `LOYALTY_OFFER`.

## Commerce — `/transactions`, `/customers`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions` | Filters: `status`, `payment_method`, `failure_code`, `customer_id`, `min_amount`, `search`, date range; paged |
| GET | `/transactions/{txn_id}` | Single transaction |
| GET | `/customers` | Search/segment-filtered customer list |
| GET | `/customers/{external_customer_id}` | AI profile: metrics, insights, recent failures |

## Analytics — `/analytics`

| Method | Path | Returns |
|--------|------|---------|
| GET | `/revenue?days=30` | KPI block + previous-period deltas (at-risk, recoverable, failure rate…) |
| GET | `/trends?days=30`   | Daily series: volume, successful vs at-risk value/counts |
| GET | `/failure-reasons`  | Failure codes ranked by value at risk + estimated recoverable |
| GET | `/payment-methods`  | Per-method success/failure rates and volumes |
| GET | `/priorities`       | Open opportunity distribution by priority |
| GET | `/segments`         | Customer LTV segments |
| GET | `/recovered-revenue`| Whole-book baseline vs AI summary (rates, ₹, multiple, retries avoided) |
| GET | `/baseline-comparison?sample_size=100` | Cohort counterfactual for top opportunities |

## AI — `/ai`

### `POST /chat` — body `{message}`

```json
{
  "answer": "You currently have ₹69L in revenue at risk…",
  "metrics": [{ "label": "Revenue at risk", "value": 6902322 }],
  "insights": ["Insufficient funds drives 34% of failures…"],
  "recommendations": ["Prioritize 12 CRITICAL/HIGH opportunities worth ₹4.2L"],
  "intent": "RECOVERY_SUMMARY",
  "tools_used": ["get_recovery_summary"]
}
```

Recognized intents: recovery summary, top opportunities, customer analysis
(`cus_*` mention), transaction status (`txn_*`), failure reasons, payment methods.
All figures come from database tools; the LLM (if configured) only rewrites prose.
