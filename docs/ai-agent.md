# AI Agent Design

## Principles

1. **Grounded, not creative.** Every number in an assistant reply comes from a
   deterministic database tool. The LLM never invents figures — it can only
   rephrase the narrative around tool output.
2. **Works offline.** `LLM_PROVIDER=mock` produces the full experience with no
   API key and zero latency/cost variance. Switching to `openai` or `groq`
   (set `*_API_KEY`) upgrades prose quality without changing any data path.
3. **Auditable.** Responses expose `intent` and `tools_used`, so judges can see
   exactly which tools produced the answer.

## Pipeline

```
message ──▶ Intent Classifier (regex + keyword rules)
                │  RECOVERY_SUMMARY | TOP_OPPORTUNITIES
                │  CUSTOMER_ANALYSIS | TRANSACTION_STATUS
                │  FAILURE_REASONS  | PAYMENT_METHODS
                ▼
        Tool Selection ──▶ Tool Execution (repositories/analytics, read-only)
                │                 get_recovery_summary()
                │                 get_top_opportunities(limit)
                │                 analyze_customer(cus_id)
                │                 get_transaction_status(txn_id)
                │                 get_failure_breakdown(days)
                │                 get_payment_method_performance()
                ▼
        Response Composer ──▶ {answer, metrics[], insights[], recommendations[]}
                │
                └─ optional LLM polish (OpenAI/Groq) on narrative text only
```

## Tools

| Tool | Source | Used for |
|------|--------|----------|
| `get_recovery_summary` | analytics.revenue_metrics | "How much can we recover?" |
| `get_top_opportunities(n)` | recovery pipeline query | "Top opportunities?" |
| `analyze_customer(cus)` | services.analyze_customer | "Tell me about cus_amit01" |
| `get_transaction_status(txn)` | transaction lookup + opportunity join | "What happened to txn_x?" |
| `get_failure_breakdown(days)` | analytics.failure_reasons | "Common failure reasons?" |
| `get_payment_method_performance()` | analytics.payment_method_performance | "Which method loses money?" |

Entity extraction: `\bcus[_-][A-Za-z0-9_]+` and `\btxn[_-][A-Za-z0-9_]+`
(the separator is required so words like "customers" don't false-match).

## Composer output contract

Each reply carries structured sections the UI renders distinctly:

- `answer` — 2–6 sentence natural response (₹ formatted Indian-style).
- `metrics[]` — chips: `{label, value}`.
- `insights[]` — observed patterns from the data.
- `recommendations[]` — concrete next actions.

## Why this beats a raw chatbot

- Deterministic → same question, same numbers, every time (demo-safe).
- No hallucinated revenue figures — the failure mode of naive RAG chatbots.
- Latency: mock provider answers in milliseconds; DB queries are indexed.
