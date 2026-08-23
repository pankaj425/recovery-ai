"""Recovery scoring, priority bands and expected-recovery arithmetic."""
from __future__ import annotations

import pytest

from app.services.failure_classifier import classify_failure
from app.services.recovery_scoring import compute_recovery_score, priority_for_score
from app.services.retry_engine import evaluate_retry_policy


def test_priority_bands():
    assert priority_for_score(95) == "CRITICAL"
    assert priority_for_score(80) == "HIGH"
    assert priority_for_score(60) == "MEDIUM"
    assert priority_for_score(10) == "LOW"


def test_score_components_sum_to_total():
    cause = classify_failure("insufficient_funds", attempt_count=2)
    result = compute_recovery_score(
        amount=25_000,
        attempt_count=2,
        lifetime_value=200_000,
        customer_successes=12,
        customer_failures=1,
        root_cause=cause,
        recovery_probability=0.7,
        hours_since_failure=6.0,
    )
    total_from_components = sum(c.points for c in result.components)
    assert abs(total_from_components - result.total) < 0.05
    assert 0 <= result.total <= 100


def test_high_value_customer_outscores_low_value_same_failure():
    cause = classify_failure("insufficient_funds", attempt_count=1)
    strong = compute_recovery_score(
        amount=25_000, attempt_count=1, lifetime_value=300_000,
        customer_successes=20, customer_failures=0, root_cause=cause,
        recovery_probability=0.8, hours_since_failure=2.0,
    )
    weak = compute_recovery_score(
        amount=2_000, attempt_count=1, lifetime_value=5_000,
        customer_successes=0, customer_failures=4, root_cause=cause,
        recovery_probability=0.3, hours_since_failure=400.0,
    )
    assert strong.total > weak.total + 30


def test_expected_recovery_value_is_amount_times_probability(seeded_database):
    from app.core.database import SessionLocal
    from app.models import RecoveryOpportunity

    with SessionLocal() as db:
        opps = db.query(RecoveryOpportunity).all()
        assert opps, "pipeline should have created opportunities"
        for opp in opps:
            expected = round(opp.revenue_at_risk * opp.recovery_probability, 2)
            assert abs(opp.expected_recovery_value - expected) < 0.01


def test_root_cause_classification():
    assert classify_failure("expired_card").root_cause == "PAYMENT_METHOD_ISSUE"
    assert classify_failure("network_error").root_cause == "BANK_OR_NETWORK"
    assert classify_failure("suspected_fraud").root_cause == "FRAUD_OR_RISK"
    repeated = classify_failure("insufficient_funds", attempt_count=3)
    assert repeated.root_cause == "CUSTOMER_BEHAVIOR"
    assert repeated.sub_cause == "repeated_attempt_failure"
    # fraud/system causes keep their family despite retries
    assert classify_failure("suspected_fraud", attempt_count=4).root_cause == "FRAUD_OR_RISK"
    assert classify_failure("gateway_error", attempt_count=4).root_cause == "SYSTEM"


def test_retry_policy_per_failure_type():
    temporary = evaluate_retry_policy("temporary_failure", 1)
    network = evaluate_retry_policy("network_error", 1)
    funds = evaluate_retry_policy("insufficient_funds", 1)
    expired = evaluate_retry_policy("expired_card", 1)
    repeated = evaluate_retry_policy("temporary_failure", 3)

    assert temporary.retry_allowed and temporary.retry_after_minutes == 30
    assert network.retry_after_minutes == 15
    assert funds.retry_allowed and funds.retry_after_minutes >= 120
    assert expired.retry_allowed is False
    assert repeated.retry_allowed is False  # 3+ attempts -> switch strategy
    for policy in (expired, repeated):
        payload = policy.to_dict()
        assert set(payload) >= {"retry_allowed", "retry_after_minutes", "reason"}


def test_weights_are_configurable():
    from app.core.config import settings

    custom = dict(settings.scoring_weights)
    custom["value"] = 50
    custom["probability"] = 5
    cause = classify_failure("insufficient_funds")
    base = compute_recovery_score(
        amount=90_000, attempt_count=1, lifetime_value=10_000,
        customer_successes=5, customer_failures=0, root_cause=cause,
        recovery_probability=0.9, hours_since_failure=1.0,
    )
    tweaked = compute_recovery_score(
        amount=90_000, attempt_count=1, lifetime_value=10_000,
        customer_successes=5, customer_failures=0, root_cause=cause,
        recovery_probability=0.9, hours_since_failure=1.0,
        weights=custom,
    )
    assert tweaked.total > base.total  # heavier value weight favors the big ticket
