"""Recovery pipeline: the heart of RecoveryAI.

    failed transaction
      -> root-cause classification        (observed facts)
      -> feature building                 (observed facts)
      -> recovery probability             (ML prediction)
      -> deterministic score + priority   (transparent formula)
      -> recommendation + retry policy    (AI suggestion)
      -> persisted opportunity + audit    (ai_decisions, score_audit)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ml.model_registry import RecoveryProbabilityModel, build_features_from_context
from app.models import RecoveryOpportunity, Transaction
from app.repositories import opportunity_repository as opp_repo
from app.repositories.customer_repository import monthly_txn_frequency_map
from app.repositories.transaction_repository import method_success_rates
from app.services.failure_classifier import RootCause, classify_failure
from app.services.recommendation_service import generate_recommendation
from app.services.retry_engine import evaluate_retry_policy
from app.services.recovery_scoring import compute_recovery_score
from app.utils.logging_config import agent_logger

logger = agent_logger("recoveryai.pipeline")


@dataclass(slots=True)
class PipelineCache:
    method_rates: dict[str, float] = field(default_factory=dict)
    customer_frequency: dict[int, float] = field(default_factory=dict)

    @classmethod
    def build(cls, db: Session) -> "PipelineCache":
        return cls(
            method_rates=method_success_rates(db),
            customer_frequency=monthly_txn_frequency_map(db),
        )


def _hours_since(dt: datetime | None) -> float:
    if dt is None:
        return 24.0
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - aware).total_seconds() / 3600.0, 0.0)


def build_explanation(
    *,
    txn: Transaction,
    cause: RootCause,
    probability: float,
    confidence: float,
    prediction_factors: list[tuple[str, float]],
    expected_recovery: float,
    priority: str,
    retry_policy: dict,
    action_message: str,
    escalation_note: str | None = None,
) -> dict:
    """The 5-part explainable-AI block shown on the detail page."""
    from app.services.failure_classifier import HUMAN_LABELS

    factor_text = ", ".join(f"{name} ({val:+.2f})" for name, val in prediction_factors[:3])
    why = (
        f"Classified as {HUMAN_LABELS[cause.root_cause]} "
        f"(root cause: {cause.root_cause}, sub-cause: {cause.sub_cause})."
    )
    if escalation_note:
        why += f" {escalation_note}"
    return {
        "what_happened": (
            f"Transaction {txn.transaction_id} of ₹{txn.amount:,.0f} via {txn.payment_method} "
            f"is {txn.status} with {txn.attempt_count} attempt(s); last failure code "
            f"'{txn.failure_code or 'checkout_abandoned'}'."
        ),
        "why": why,
        "prediction": (
            f"Model estimates a {probability:.0%} chance of successful recovery "
            f"(confidence {confidence:.0%}). Strongest drivers: {factor_text or 'n/a'}."
        ),
        "action": (
            f"{action_message} Retry policy: "
            + (
                f"retry allowed after {retry_policy['retry_after_minutes']} minutes."
                if retry_policy.get("retry_allowed")
                else "auto-retry disabled; use the recommended alternative workflow."
            )
        ),
        "impact": (
            f"Expected recovery value ₹{expected_recovery:,.0f} at {priority} priority "
            f"(₹{txn.amount:,.0f} at risk × {probability:.0%} probability)."
        ),
    }


def apply_priority_rules(
    *,
    priority: str,
    score: float,
    root_cause: RootCause,
    amount: float,
    customer_successes: int,
) -> tuple[str, str | None]:
    """Transparent business rules layered on top of the deterministic score.

    Rule 1: A fraud/risk block on a proven, high-value order is treated as a
    revenue emergency -> escalate to CRITICAL (manual review, not auto-retry).
    Returns (final_priority, escalation_reason|None).
    """
    if (
        root_cause.root_cause == "FRAUD_OR_RISK"
        and amount >= 50_000
        and customer_successes >= 10
        and priority != "CRITICAL"
    ):
        return "CRITICAL", (
            "Escalated to CRITICAL by business rule: risk-engine decline on a "
            f"proven customer (\u20b9{amount:,.0f} order, {customer_successes} prior successful payments) - "
            "likely false positive requiring immediate manual review."
        )
    return priority, None


def run_recovery_pipeline(
    db: Session,
    txn: Transaction,
    cache: PipelineCache | None = None,
) -> RecoveryOpportunity:
    """Score one failed/abandoned transaction and upsert its recovery opportunity."""
    cache = cache or PipelineCache()
    customer = txn.customer

    cause = classify_failure(txn.failure_code, txn.attempt_count, txn.status)
    hours_since = _hours_since(txn.created_at)

    features = build_features_from_context(
        amount=txn.amount,
        attempt_count=txn.attempt_count,
        lifetime_value=customer.lifetime_value,
        customer_successes=customer.successful_transactions,
        customer_failures=customer.failed_transactions,
        method_success_rate=cache.method_rates.get(txn.payment_method, 0.6),
        cause_prior=cause.recoverability_prior,
        hours_since_failure=hours_since,
        txn_frequency_per_month=cache.customer_frequency.get(customer.id, 1.0),
    )

    prediction = RecoveryProbabilityModel.get().predict(features)
    probability = round(prediction.probability, 4)
    expected_recovery = round(txn.amount * probability, 2)

    score_result = compute_recovery_score(
        amount=txn.amount,
        attempt_count=txn.attempt_count,
        lifetime_value=customer.lifetime_value,
        customer_successes=customer.successful_transactions,
        customer_failures=customer.failed_transactions,
        root_cause=cause,
        recovery_probability=probability,
        hours_since_failure=hours_since,
    )
    score_breakdown = score_result.breakdown_dict()
    priority, escalation_note = apply_priority_rules(
        priority=score_result.priority,
        score=score_result.total,
        root_cause=cause,
        amount=txn.amount,
        customer_successes=customer.successful_transactions,
    )
    if escalation_note:
        score_breakdown["escalation"] = escalation_note

    recommendation = generate_recommendation(
        cause,
        amount=txn.amount,
        lifetime_value=customer.lifetime_value,
        attempt_count=txn.attempt_count,
        recovery_probability=probability,
    )
    retry_policy = evaluate_retry_policy(cause.sub_cause, txn.attempt_count).to_dict()

    explanation = build_explanation(
        txn=txn,
        cause=cause,
        probability=probability,
        confidence=prediction.confidence,
        prediction_factors=prediction.factors,
        expected_recovery=expected_recovery,
        priority=priority,
        retry_policy=retry_policy,
        action_message=recommendation.message,
        escalation_note=escalation_note,
    )

    opportunity = opp_repo.get_by_transaction(db, txn.id)
    if opportunity is None:
        opportunity = RecoveryOpportunity(transaction_id=txn.id, customer_id=customer.id)
        db.add(opportunity)

    opportunity.revenue_at_risk = round(txn.amount, 2)
    opportunity.recovery_probability = probability
    opportunity.expected_recovery_value = expected_recovery
    opportunity.recovery_score = score_result.total
    opportunity.priority = priority
    opportunity.root_cause = cause.root_cause
    opportunity.sub_cause = cause.sub_cause
    opportunity.recommended_action = recommendation.action_type
    opportunity.explanation = explanation
    opportunity.retry_policy = retry_policy
    opportunity.model_version = prediction.model_version

    db.flush()
    opp_repo.record_audit(
        db,
        opportunity=opportunity,
        score_breakdown=score_breakdown,
        weights=dict(_current_weights()),
        features_snapshot=features.to_dict(),
        prediction=prediction.to_dict(),
        recommendation={
            "action_type": recommendation.action_type,
            "channel": recommendation.channel,
            "message": recommendation.message,
            "requires_approval": recommendation.requires_approval,
        },
        confidence=prediction.confidence,
        model_version=prediction.model_version,
    )
    logger.info(
        "opportunity_scored",
        extra={
            "transaction_id": txn.transaction_id,
            "customer_id": customer.external_customer_id,
            "root_cause": cause.sub_cause,
            "probability": probability,
            "score": score_result.total,
            "priority": score_result.priority,
            "expected_recovery": expected_recovery,
        },
    )
    return opportunity


def _current_weights() -> dict[str, float]:
    from app.core.config import settings

    return settings.scoring_weights
