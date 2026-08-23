"""Feature engineering for the recovery-probability model.

Features are deliberately few, bounded and human-readable so every
prediction can be explained as a sum of named contributions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

FEATURE_NAMES: tuple[str, ...] = (
    "log_amount",
    "attempt_pressure",
    "log_ltv",
    "customer_success_rate",
    "method_success_rate",
    "cause_prior",
    "recency_factor",
    "txn_frequency",
)

# Reference constants (documented; used for normalization only).
RECENCY_HALF_LIFE_HOURS = 72.0
MAX_ATTEMPTS_REF = 5
MAX_TXN_FREQ_REF = 20  # transactions per month


@dataclass(slots=True)
class RecoveryFeatures:
    amount: float
    attempt_count: int
    lifetime_value: float
    customer_successes: int
    customer_failures: int
    method_success_rate: float  # historical success rate of the payment method [0..1]
    cause_prior: float  # empirical recoverability prior for the failure code [0..1]
    hours_since_failure: float
    txn_frequency_per_month: float

    def to_vector(self) -> list[float]:
        cust_total = max(self.customer_successes + self.customer_failures, 1)
        return [
            math.log10(max(self.amount, 1.0)),
            min(self.attempt_count / MAX_ATTEMPTS_REF, 1.0),
            math.log10(max(self.lifetime_value, 1.0)),
            self.customer_successes / cust_total,
            _clip01(self.method_success_rate),
            _clip01(self.cause_prior),
            math.exp(-self.hours_since_failure / RECENCY_HALF_LIFE_HOURS),
            min(self.txn_frequency_per_month / MAX_TXN_FREQ_REF, 1.0),
        ]

    def to_dict(self) -> dict:
        return asdict(self)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))
