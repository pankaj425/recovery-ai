"""Actionable recommendation mapping per failure type + customer context."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.failure_classifier import RootCause

HIGH_VALUE_LTV = 100_000.0
HIGH_VALUE_AMOUNT = 50_000.0

_ACTION_TABLE: dict[str, tuple[str, str]] = {
    # sub_cause: (action_type, channel)
    "insufficient_funds": ("DELAYED_RETRY", "RETRY"),
    "temporary_failure": ("INTELLIGENT_RETRY", "RETRY"),
    "bank_timeout": ("INTELLIGENT_RETRY", "RETRY"),
    "network_error": ("INTELLIGENT_RETRY", "RETRY"),
    "gateway_error": ("INTELLIGENT_RETRY", "RETRY"),
    "expired_card": ("UPDATE_PAYMENT_METHOD", "EMAIL"),
    "invalid_card": ("UPDATE_PAYMENT_METHOD", "EMAIL"),
    "payment_method_declined": ("ALTERNATIVE_PAYMENT_METHOD", "WHATSAPP"),
    "repeated_attempt_failure": ("ESCALATE_OUTREACH", "MANUAL_REVIEW"),
    "abandoned_checkout": ("RECOVERY_CAMPAIGN", "EMAIL"),
    "suspected_fraud": ("MANUAL_RISK_REVIEW", "MANUAL_REVIEW"),
    "false_positive": ("MANUAL_RISK_REVIEW", "MANUAL_REVIEW"),
    "unknown": ("MANUAL_REVIEW", "MANUAL_REVIEW"),
}


@dataclass(slots=True)
class Recommendation:
    action_type: str
    channel: str
    message: str
    requires_approval: bool


def generate_recommendation(
    root_cause: RootCause,
    *,
    amount: float,
    lifetime_value: float,
    attempt_count: int,
    recovery_probability: float,
) -> Recommendation:
    action, channel = _ACTION_TABLE.get(root_cause.sub_cause, _ACTION_TABLE["unknown"])
    high_value = lifetime_value >= HIGH_VALUE_LTV or amount >= HIGH_VALUE_AMOUNT

    if high_value:
        action = f"PRIORITIZE_{action}"
        channel = "MANUAL_REVIEW" if channel == "RETRY" else channel
        message = (
            f"High-value opportunity (amount ₹{amount:,.0f}, LTV ₹{lifetime_value:,.0f}). "
            f"Recommended: {action.replace('_', ' ').title()} - immediate personalized outreach "
            f"alongside the {root_cause.sub_cause.replace('_', ' ')} playbook."
        )
    elif root_cause.sub_cause == "repeated_attempt_failure":
        message = (
            f"{attempt_count} failed attempts detected. Stop same-method retries; "
            "switch to an alternative payment method and start customer outreach."
        )
    elif action in ("INTELLIGENT_RETRY", "DELAYED_RETRY"):
        message = (
            f"Failure classified as '{root_cause.sub_cause}' (model recovery probability "
            f"{recovery_probability:.0%}). Schedule one smart retry per policy instead of blind retries."
        )
    else:
        message = f"Run the {action.replace('_', ' ').lower().title()} workflow for this failure type."

    return Recommendation(
        action_type=action,
        channel=channel,
        message=message,
        # Any customer-affecting outreach or retry needs a human click.
        requires_approval=True,
    )
