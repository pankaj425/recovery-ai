"""ML model tests: deterministic training, sane probabilities, explainability."""
from __future__ import annotations

from app.ml.features import RecoveryFeatures
from app.ml.model_registry import MODEL_VERSION, RecoveryProbabilityModel, train_model
from app.services.failure_classifier import classify_failure


def _features(**overrides) -> RecoveryFeatures:
    base = dict(
        amount=25_000.0,
        attempt_count=3,
        lifetime_value=180_000.0,
        customer_successes=11,
        customer_failures=1,
        method_success_rate=0.72,
        cause_prior=0.58,
        hours_since_failure=8.0,
        txn_frequency_per_month=4.0,
    )
    base.update(overrides)
    return RecoveryFeatures(**base)


def test_training_is_deterministic():
    m1 = train_model()
    m2 = train_model()
    assert m1.weights == m2.weights
    assert abs(m1.bias - m2.bias) < 1e-12


def test_probability_within_bounds_and_versioned():
    result = RecoveryProbabilityModel.get().predict(_features())
    assert 0.0 <= result.probability <= 1.0
    assert 0.5 <= result.confidence <= 0.95
    assert result.model_version == MODEL_VERSION


def test_strong_history_beats_weak_history():
    strong = RecoveryProbabilityModel.get().predict(
        _features(customer_successes=20, customer_failures=0, lifetime_value=300_000, attempt_count=1)
    )
    weak = RecoveryProbabilityModel.get().predict(
        _features(customer_successes=0, customer_failures=5, lifetime_value=5_000, attempt_count=4)
    )
    assert strong.probability > weak.probability + 0.15


def test_more_attempts_lower_recovery_odds():
    one = RecoveryProbabilityModel.get().predict(_features(attempt_count=1)).probability
    four = RecoveryProbabilityModel.get().predict(_features(attempt_count=4)).probability
    assert one > four


def test_top_factors_provided_for_explanations():
    cause = classify_failure("insufficient_funds")
    features = _features(cause_prior=cause.recoverability_prior)
    result = RecoveryProbabilityModel.get().predict(features)
    names = {name for name, _ in result.factors}
    assert len(result.factors) == 4
    assert all(name in set(
        ["log_amount", "attempt_pressure", "log_ltv", "customer_success_rate",
         "method_success_rate", "cause_prior", "recency_factor", "txn_frequency"]
    ) for name in names)


def test_prediction_dict_shape():
    payload = RecoveryProbabilityModel.get().predict(_features()).to_dict()
    assert set(payload) >= {"recovery_probability", "confidence", "model_version", "top_factors"}
