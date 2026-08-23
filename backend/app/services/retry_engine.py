"""Smart retry engine: never retry everything at the same interval."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class RetryPolicy:
    retry_allowed: bool
    retry_after_minutes: int | None
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


_POLICY: dict[str, RetryPolicy] = {
    "temporary_failure": RetryPolicy(True, 30, "Temporary bank failure pattern"),
    "bank_timeout": RetryPolicy(True, 30, "Bank timeout pattern"),
    "network_error": RetryPolicy(True, 15, "Network failure pattern"),
    "insufficient_funds": RetryPolicy(True, 180, "Funds may become available later; delay retry by several hours"),
    "abandoned_checkout": RetryPolicy(True, 240, "Recovery reminder after checkout abandonment"),
    "gateway_error": RetryPolicy(True, 60, "Gateway-side error usually resolves quickly"),
    "expired_card": RetryPolicy(False, None, "Card expired - auto-retry pointless; request payment-method update"),
    "invalid_card": RetryPolicy(False, None, "Invalid card details - require updated payment method"),
    "payment_method_declined": RetryPolicy(False, None, "Issuer declined - offer alternative payment method"),
    "suspected_fraud": RetryPolicy(False, None, "Risk hold - requires manual review before any retry"),
    "false_positive": RetryPolicy(False, None, "Risk false positive - escalate for manual risk review"),
    "repeated_attempt_failure": RetryPolicy(False, None, "3+ failed attempts - escalate to alternative method/outreach"),
    "unknown": RetryPolicy(False, None, "Unclassified failure - manual inspection required"),
}


def evaluate_retry_policy(sub_cause: str | None, attempt_count: int = 1) -> RetryPolicy:
    policy = _POLICY.get(sub_cause or "", _POLICY["unknown"])
    if attempt_count >= 3 and policy.retry_allowed:
        return RetryPolicy(
            False,
            None,
            f"{policy.reason}; but {attempt_count} attempts already made - switch strategy",
        )
    return policy
