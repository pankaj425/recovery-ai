"""Root-cause engine: maps low-level provider failure codes to business causes."""
from __future__ import annotations

from dataclasses import dataclass

ROOT_CAUSES = (
    "PAYMENT_METHOD_ISSUE",
    "BANK_OR_NETWORK",
    "FRAUD_OR_RISK",
    "CUSTOMER_BEHAVIOR",
    "SYSTEM",
)

FAILURE_CODE_TO_CAUSE: dict[str, tuple[str, str]] = {
    "expired_card": ("PAYMENT_METHOD_ISSUE", "expired_card"),
    "invalid_card": ("PAYMENT_METHOD_ISSUE", "invalid_card"),
    "insufficient_funds": ("PAYMENT_METHOD_ISSUE", "insufficient_funds"),
    "payment_method_declined": ("PAYMENT_METHOD_ISSUE", "payment_method_declined"),
    "bank_timeout": ("BANK_OR_NETWORK", "bank_timeout"),
    "network_error": ("BANK_OR_NETWORK", "network_error"),
    "temporary_failure": ("BANK_OR_NETWORK", "temporary_failure"),
    "suspected_fraud": ("FRAUD_OR_RISK", "suspected_fraud"),
    "risk_rule_false_positive": ("FRAUD_OR_RISK", "false_positive"),
    "abandoned_checkout": ("CUSTOMER_BEHAVIOR", "abandoned_checkout"),
    "gateway_error": ("SYSTEM", "gateway_error"),
    "integration_error": ("SYSTEM", "integration_error"),
}

DEFAULT_CAUSE: tuple[str, str] = ("SYSTEM", "unknown")

# Empirical recoverability prior per sub-cause (feeds ML feature `cause_prior`
# and baseline comparisons). Values are assumptions, not measurements.
CAUSE_RECOVERABILITY_PRIOR: dict[str, float] = {
    "temporary_failure": 0.72,
    "network_error": 0.68,
    "bank_timeout": 0.66,
    "insufficient_funds": 0.58,
    "false_positive": 0.70,
    "expired_card": 0.52,
    "abandoned_checkout": 0.46,
    "gateway_error": 0.50,
    "payment_method_declined": 0.38,
    "invalid_card": 0.32,
    "suspected_fraud": 0.28,
    "repeated_attempt_failure": 0.40,
    "unknown": 0.40,
}


@dataclass(slots=True)
class RootCause:
    root_cause: str
    sub_cause: str

    @property
    def recoverability_prior(self) -> float:
        return CAUSE_RECOVERABILITY_PRIOR.get(self.sub_cause, CAUSE_RECOVERABILITY_PRIOR["unknown"])


def classify_failure(failure_code: str | None, attempt_count: int = 1, status: str = "FAILED") -> RootCause:
    """Deterministic classification of a failed/incomplete payment.

    Rules (in order):
    1. ABANDONED status          -> CUSTOMER_BEHAVIOR / abandoned_checkout
    2. >= 3 attempts             -> CUSTOMER_BEHAVIOR / repeated_attempt_failure
       (except FRAUD_OR_RISK and SYSTEM causes, which stay put)
    3. otherwise                 -> code mapping table
    """
    cause, sub = FAILURE_CODE_TO_CAUSE.get((failure_code or "").lower(), DEFAULT_CAUSE)
    if status == "ABANDONED":
        return RootCause("CUSTOMER_BEHAVIOR", "abandoned_checkout")
    if attempt_count >= 3 and cause not in ("FRAUD_OR_RISK", "SYSTEM"):
        return RootCause("CUSTOMER_BEHAVIOR", "repeated_attempt_failure")
    return RootCause(cause, sub)


HUMAN_LABELS: dict[str, str] = {
    "PAYMENT_METHOD_ISSUE": "Payment-method problem",
    "BANK_OR_NETWORK": "Bank or network issue",
    "FRAUD_OR_RISK": "Fraud/risk engine block",
    "CUSTOMER_BEHAVIOR": "Customer behaviour",
    "SYSTEM": "System/gateway error",
}
