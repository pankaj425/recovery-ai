"""Agent orchestrator: intent -> plan -> tool execution -> composed answer.

Response contract: {answer, metrics[], insights[], recommendations[], intent,
tools_used}. Numbers always originate from tool output; the LLM (if any) only
rephrases the deterministic draft.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.agents import intent as intents
from app.agents import tools
from app.agents.llm_providers import get_llm_provider, refine_answer
from app.utils.formatting import compact_inr, inr, pct
from app.utils.logging_config import agent_logger

logger = agent_logger("recoveryai.orchestrator")

_SUGGESTED_QUESTIONS = [
    "How much revenue can we potentially recover?",
    "Which customers should I prioritize today?",
    "Why did payment failures increase this week?",
    "Which payment method is causing the most revenue loss?",
]


@dataclass(slots=True)
class AgentResult:
    answer: str
    metrics: list[dict[str, Any]] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    intent: str = "HELP"
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "metrics": self.metrics,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "intent": self.intent,
            "tools_used": self.tools_used,
        }


def _plan(message: str) -> tuple[str, list[tuple[str, dict]]]:
    """Return (intent, ordered [(tool_name, params)])."""
    text = message.lower()
    customer_id = intents.extract_customer_id(message)
    method = intents.extract_method(message)
    days = intents.extract_days(message)
    limit = intents.extract_limit(message)

    if customer_id:
        return "CUSTOMER_DETAIL", [("analyze_customer", {"customer_id": customer_id})]
    intent = intents.classify_intent(message)

    if intent == "RECOVERABLE_REVENUE":
        return intent, [
            ("get_revenue_metrics", {"days": days}),
            ("get_recovery_opportunities", {"limit": max(limit, 3)}),
        ]
    if intent == "TOP_OPPORTUNITIES":
        return intent, [
            ("get_recovery_opportunities", {"limit": limit}),
            ("get_failure_reasons", {"days": days}),
        ]
    if intent == "CRITICAL_OPPORTUNITIES":
        return intent, [("get_recovery_opportunities", {"priority": "CRITICAL,HIGH", "limit": limit})]
    if intent == "FAILURE_REASONS":
        return intent, [("get_failure_reasons", {"days": days}), ("get_revenue_metrics", {"days": days})]
    if intent == "PAYMENT_METHOD_ANALYSIS":
        return intent, [("analyze_payment_method", {"method": method}), ("get_recovery_opportunities", {"limit": 3})]
    if intent == "CUSTOMER_PRIORITIZATION":
        return intent, [("get_recovery_opportunities", {"priority": "CRITICAL,HIGH,MEDIUM", "limit": 8})]
    if intent == "WEEK_COMPARISON":
        return intent, [("compare_weekly_recovery", {})]
    if intent == "REVENUE_LOSS":
        return intent, [
            ("get_revenue_metrics", {"days": days}),
            ("get_failure_reasons", {"days": days}),
            ("get_recovery_opportunities", {"limit": 3}),
        ]
    return "HELP", []


# --------------------------------------------------------------------------- #
def _compose(intent: str, results: dict[str, Any], question: str) -> AgentResult:
    composer = _COMPOSERS.get(intent, _compose_help)
    result = composer(results, question)
    result.intent = intent
    result.tools_used = [name for name in results.keys() if name != "_failed"]
    return result


def _compose_recoverable(res: dict, _: str) -> AgentResult:
    m = res["get_revenue_metrics"]
    opps = res["get_recovery_opportunities"]
    lines = [
        f"You currently have {inr(m['revenue_at_risk'])} in revenue at risk.",
        "",
        f"Based on transaction history and recovery probability, approximately "
        f"{inr(m['potential_recoverable_revenue'])} is potentially recoverable "
        f"({pct(m['recovery_rate'])} of at-risk value).",
    ]
    if opps:
        lines.append("")
        lines.append("Top opportunities:")
        for i, o in enumerate(opps[:5], 1):
            lines.append(
                f"{i}. {compact_inr(o['expected_recovery_value'])} - {o['customer_name']} "
                f"({o['priority']}, {pct(o['recovery_probability'])} probability)"
            )
    metrics = [
        {"label": "Revenue at Risk", "value": inr(m["revenue_at_risk"])},
        {"label": "Potentially Recoverable", "value": inr(m["potential_recoverable_revenue"])},
        {"label": "Estimated Recovery Rate", "value": pct(m["recovery_rate"], 1)},
        {"label": "Open Failure Rate", "value": pct(m["failure_rate"], 1)},
    ]
    insights = [
        "Recovery values are model estimates (P(recovery) x amount), not guaranteed outcomes."
    ]
    recs = (
        [
            f"Start with {opps[0]['customer_name']} ({opps[0]['priority']}): "
            f"{opps[0]['recommended_action'].replace('_', ' ').lower()} worth {inr(opps[0]['expected_recovery_value'])}."
        ]
        if opps
        else ["No open opportunities right now."]
    )
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_opportunities(res: dict, _: str) -> AgentResult:
    opps = res["get_recovery_opportunities"]
    reasons = res.get("get_failure_reasons") or []
    lines = [f"Top {len(opps)} recovery opportunities by expected value: ", ""]
    for i, o in enumerate(opps, 1):
        lines.append(
            f"{i}. [{o['priority']}] {o['customer_name']} - {inr(o['amount_at_risk'])} at risk, "
            f"{pct(o['recovery_probability'])} chance to recover {compact_inr(o['expected_recovery_value'])} "
            f"(cause: {o['sub_cause']})"
        )
    top_reason = reasons[0] if reasons else None
    insights = (
        [f"Largest loss concentration: '{top_reason['code']}' ({pct(top_reason['share_of_loss'])} of at-risk value)."]
        if top_reason
        else []
    )
    metrics = [
        {"label": f"#{i + 1} Expected Recovery", "value": inr(o["expected_recovery_value"])}
        for i, o in enumerate(opps[:4])
    ]
    recs = [f"Work {o['customer_name']}: {o['recommended_action'].replace('_', ' ').lower()}" for o in opps[:2]]
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_critical(res: dict, _: str) -> AgentResult:
    opps = res["get_recovery_opportunities"]
    critical = [o for o in opps if o["priority"] == "CRITICAL"]
    high = [o for o in opps if o["priority"] == "HIGH"]
    header = (
        f"There are {len(critical)} CRITICAL and {len(high)} additional HIGH-priority opportunities."
        if opps
        else "No critical or high priority opportunities are currently open."
    )
    lines = [header, ""]
    for o in opps[:6]:
        lines.append(
            f"- [{o['priority']}] {o['customer_name']} - {inr(o['amount_at_risk'])} | "
            f"recover {compact_inr(o['expected_recovery_value'])} @ {pct(o['recovery_probability'])}"
        )
    metrics = [{"label": "Critical count", "value": len(critical)}, {"label": "High count", "value": len(high)}]
    recs = [f"Act on {critical[0]['customer_name']} first." if critical else "Keep monitoring the queue."]
    return AgentResult("\n".join(lines), metrics, [], recs)


def _compose_failures(res: dict, _: str) -> AgentResult:
    reasons = res.get("get_failure_reasons") or []
    m = res.get("get_revenue_metrics") or {}
    total_at_risk = sum(r["value_at_risk"] for r in reasons)
    lines = [
        f"{len(reasons)} distinct failure causes account for {inr(total_at_risk)} at risk.",
        "",
    ]
    for r in reasons[:5]:
        lines.append(
            f"- {r['code']}: {r['count']} failures, {inr(r['value_at_risk'])} "
            f"({pct(r['share_of_loss'])}); est. recoverable {inr(r['estimated_recoverable'])}"
        )
    metrics = [
        {"label": "Revenue at risk", "value": inr(m.get("revenue_at_risk", total_at_risk))},
        {"label": "Failure rate", "value": pct(m.get("failure_rate", 0), 1)},
    ]
    top = reasons[0] if reasons else None
    insights = [f"'{top['code']}' drives {pct(top['share_of_loss'])} of losses." if top else ""]
    recs = (
        ["Prioritize the top cause's playbook first; each cause maps to a different recovery action."]
        if top
        else []
    )
    return AgentResult("\n".join(filter(None, lines)), metrics, list(filter(None, insights)), recs)


def _compose_methods(res: dict, _: str) -> AgentResult:
    rows = res.get("analyze_payment_method") or []
    opps = res.get("get_recovery_opportunities") or []
    if isinstance(rows, dict):
        rows = [rows]
    worst = rows[0] if rows else None
    lines = ["Payment-method performance by revenue lost:", ""]
    for r in rows[:5]:
        lines.append(
            f"- {r['method']}: success {pct(r['success_rate'], 1)}, lost {inr(r['revenue_lost'])}, "
            f"est. recoverable {inr(r['estimated_recoverable'])}"
        )
    metrics = [
        {"label": f"{r['method']} failure rate", "value": pct(r["failure_rate"], 1)} for r in rows[:4]
    ]
    insights = (
        [f"{worst['method']} loses the most revenue ({inr(worst['revenue_lost'])})."] if worst else []
    )
    recs = (
        [f"Route high-value retries away from {worst['method']} toward your best-performing method."]
        if worst
        else []
    )
    _ = opps
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_prioritize(res: dict, _: str) -> AgentResult:
    opps = res.get("get_recovery_opportunities") or []
    lines = ["Today's priority list (by expected recovery value):", ""]
    for i, o in enumerate(opps, 1):
        lines.append(
            f"{i}. {o['customer_name']} ({o['customer_id']}) - {inr(o['amount_at_risk'])} at risk, "
            f"{o['attempts']} attempts, {pct(o['recovery_probability'])} to recover "
            f"{compact_inr(o['expected_recovery_value'])} [{o['priority']}]"
        )
    metrics = [{"label": "Opportunities listed", "value": len(opps)}]
    insights = ["Ranking combines value, ML recovery probability and customer history - not amount alone."]
    recs = [f"Call {opps[0]['customer_name']} first; expected impact {inr(opps[0]['expected_recovery_value'])}."] if opps else []
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_customer_detail(res: dict, _: str) -> AgentResult:
    data = res.get("analyze_customer")
    if not data:
        return AgentResult("I could not find that customer. Use an id like cus_1001.", [], [], [])
    c = data["customer"]
    methods = data["payment_methods"]
    best_method = methods[0]["method"] if methods else "n/a"
    opps = data["open_recovery_opportunities"]
    lines = [
        f"{c['name']} ({c['id']}) - segment {c['segment']}, LTV {inr(c['lifetime_value'])}.",
        f"History: {c['successful_transactions']} successful / {c['failed_transactions']} failed transactions.",
        f"Best-performing method historically: {best_method} "
        f"({pct(methods[0]['success_rate'], 0)} success) .",
    ]
    if opps:
        o = opps[0]
        lines.append(
            f"\nOpen opportunity: {inr(o['amount'])} at risk, estimated {pct(o['probability'])} "
            f"recoverable ({inr(o['expected_recovery'])}) due to {o['sub_cause']}."
        )
    metrics = [
        {"label": "Lifetime value", "value": inr(c["lifetime_value"])},
        {"label": "Successful txns", "value": c["successful_transactions"]},
        {"label": "Failed txns", "value": c["failed_transactions"]},
    ]
    insights = [
        "Predictions above are model estimates based on this customer's observed payment history.",
    ]
    recs = (
        [f"Recommended: pursue with a {opps[0]['sub_cause']} recovery play before generic retries."]
        if opps
        else ["No open recovery opportunities for this customer."]
    )
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_weekly(res: dict, _: str) -> AgentResult:
    w = res["compare_weekly_recovery"]
    this, last = w["this_week"], w["last_week"]
    change = w["rate_change_pp"]
    direction = "improved" if change >= 0 else "declined"
    lines = [
        f"This week's AI-assisted recovery rate is {pct(this['ai_assisted_recovery_rate'], 1)} "
        f"vs {pct(last['ai_assisted_recovery_rate'], 1)} last week ({direction} by {abs(change):.1f} pp).",
        f"At-risk volume moved from {inr(last['revenue_at_risk'])} to {inr(this['revenue_at_risk'])}; "
        f"estimated recoverable value {inr(this['ai_assisted_recovered_revenue'])} vs {inr(last['ai_assisted_recovered_revenue'])}.",
        "",
        f"For reference, the rule-based baseline would recover about "
        f"{pct(this['baseline_recovery_rate'], 1)} this week.",
    ]
    metrics = [
        {"label": "This week rate", "value": pct(this["ai_assisted_recovery_rate"], 1)},
        {"label": "Last week rate", "value": pct(last["ai_assisted_recovery_rate"], 1)},
        {"label": "Change (pp)", "value": round(change, 1)},
    ]
    insights = ["Rates compare estimated recoverable value against at-risk value per window."]
    recs = ["Review newly created HIGH/CRITICAL opportunities weekly to sustain the uplift."]
    return AgentResult("\n".join(lines), metrics, insights, recs)


def _compose_help(_: dict, __: str) -> AgentResult:
    lines = [
        "I'm RecoveryAI's merchant assistant. I answer questions using live platform data via backend tools.",
        "",
        "Try:",
        "- How much revenue are we losing?",
        "- Show me the top recovery opportunities.",
        "- Which customers should I prioritize today?",
        "- Which payment method causes the most revenue loss?",
        "- Compare this week's recovery performance with last week.",
    ]
    return AgentResult("\n".join(lines), [], [], [])


_COMPOSERS = {
    "RECOVERABLE_REVENUE": _compose_recoverable,
    "TOP_OPPORTUNITIES": _compose_opportunities,
    "CRITICAL_OPPORTUNITIES": _compose_critical,
    "FAILURE_REASONS": _compose_failures,
    "PAYMENT_METHOD_ANALYSIS": _compose_methods,
    "CUSTOMER_PRIORITIZATION": _compose_prioritize,
    "CUSTOMER_DETAIL": _compose_customer_detail,
    "WEEK_COMPARISON": _compose_weekly,
    "HELP": _compose_help,
}


def handle_chat(db: Session, message: str) -> dict:
    intent, plan = _plan(message)
    executed: dict[str, Any] = {}
    failed: list[str] = []
    for tool_name, params in plan:
        handler = tools.TOOL_HANDLERS.get(tool_name)
        try:
            if handler is None:
                raise KeyError(tool_name)
            outcome = handler(db, **params)
            if outcome is None:
                raise ValueError(f"{tool_name} returned no data")
            executed[tool_name] = outcome if not isinstance(outcome, tuple) else outcome[0]
        except Exception as exc:  # noqa: BLE001 - one tool failing must not kill the answer
            logger.warning("tool_failed", extra={"tool": tool_name, "error": str(exc)})
            failed.append(tool_name)

    if not executed:
        result = _compose_help({}, message)
        result.intent = intent
    else:
        result = _compose(intent, executed, message)

    provider = get_llm_provider()
    if provider.name != "mock":
        refined = refine_answer(provider, question=message, context=executed, draft=result.answer)
        result.answer = refined

    logger.info(
        "chat_answered",
        extra={"intent": intent, "tools_used": ",".join(result.tools_used), "failed_tools": ",".join(failed)},
    )
    payload = result.to_dict()
    payload["suggested_questions"] = _SUGGESTED_QUESTIONS
    return payload
