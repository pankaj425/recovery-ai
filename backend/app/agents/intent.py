"""Rule-based intent classification for merchant questions (fast + auditable)."""
from __future__ import annotations

import re

INTENTS = (
    "RECOVERABLE_REVENUE",
    "REVENUE_LOSS",
    "TOP_OPPORTUNITIES",
    "CRITICAL_OPPORTUNITIES",
    "FAILURE_REASONS",
    "PAYMENT_METHOD_ANALYSIS",
    "CUSTOMER_PRIORITIZATION",
    "CUSTOMER_DETAIL",
    "WEEK_COMPARISON",
    "HELP",
)

_CUSTOMER_ID = re.compile(r"\bcus[_\-][A-Za-z0-9_]+", re.IGNORECASE)
_METHODS = {"upi": "UPI", "card": "CARD", "netbanking": "NETBANKING", "net banking": "NETBANKING", "wallet": "WALLET"}

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("RECOVERABLE_REVENUE", ("recoverable", "recovered", "how much revenue could", "can we recover", "potential recovery")),
    ("WEEK_COMPARISON", ("this week", "last week", "compare", "week over week")),
    ("CRITICAL_OPPORTUNITIES", ("critical",)),
    ("TOP_OPPORTUNITIES", ("top 10", "top opportunities", "top recovery", "show me the top", "best opportunities")),
    ("FAILURE_REASONS", ("why did payment failures", "why are we losing", "top causes", "failure reasons", "reasons for failure", "causes of failed")),
    ("PAYMENT_METHOD_ANALYSIS", ("payment method", "payment methods", "method causing", *_METHODS.keys())),
    ("CUSTOMER_DETAIL", ()),  # matched via regex below
    ("CUSTOMER_PRIORITIZATION", ("which customers", "prioritize", "who should i contact", "focus on today", "prioritize today")),
    ("REVENUE_LOSS", ("losing", "loss", "at risk", "leakage", "failing payments cost", "failed payments costing")),
]


def extract_customer_id(message: str) -> str | None:
    match = _CUSTOMER_ID.search(message)
    return match.group(0) if match else None


def extract_method(message: str) -> str | None:
    lowered = message.lower()
    for key, method in _METHODS.items():
        if key in lowered:
            return method
    return None


def extract_limit(message: str, default: int = 5) -> int:
    match = re.search(r"top\s+(\d+)", message.lower())
    return min(int(match.group(1)) if match else default, 25)


def classify_intent(message: str) -> str:
    text = message.lower().strip()
    if extract_customer_id(text):
        return "CUSTOMER_DETAIL"
    if any(k in text for k in ("how much revenue can", "potentially be recovered", "could potentially")) and "recover" in text:
        return "RECOVERABLE_REVENUE"
    for intent, keywords in _RULES:
        if keywords and any(k in text for k in keywords):
            return intent
    if "fail" in text or "losing" in text or "risk" in text:
        return "REVENUE_LOSS"
    if "recover" in text:
        return "RECOVERABLE_REVENUE"
    if "opportunit" in text:
        return "TOP_OPPORTUNITIES"
    return "HELP"


def extract_days(message: str) -> int:
    text = message.lower()
    if "week" in text:
        return 7
    if "month" in text:
        return 30
    if "today" in text or "yesterday" in text:
        return 1
    return 30
