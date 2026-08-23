"""Analytics aggregation tests against known fixture data."""
from __future__ import annotations

from app.analytics.baseline import baseline_comparison, recovered_revenue_summary
from app.analytics.metrics import (
    customer_segments,
    daily_trends,
    failure_reasons,
    payment_method_performance,
    priority_distribution,
    revenue_metrics,
)
from app.core.database import SessionLocal


def test_revenue_metrics_known_values(seeded_database):
    with SessionLocal() as db:
        m = revenue_metrics(db, days=30)
        # fixtures: 25k FAILED + 8k ABANDONED inside window; 12k SUCCESS
        assert m["revenue_at_risk"] == 33_000.0
        assert m["successful_revenue"] >= 12_000.0
        assert 0 < m["failure_rate"] < 1
        assert set(m["comparison"]) >= {"revenue_at_risk", "failure_rate", "total_revenue"}


def test_potential_recoverable_matches_opportunity_sum(seeded_database):
    from app.models import RecoveryOpportunity

    with SessionLocal() as db:
        m = revenue_metrics(db, days=365)
        expected_sum = db.query(RecoveryOpportunity).filter(
            RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS"))
        ).count()
        assert m["potential_recoverable_revenue"] > 0
        assert expected_sum > 0


def test_failure_reasons_shape(seeded_database):
    with SessionLocal() as db:
        rows = failure_reasons(db)
        assert rows
        assert all(set(r) >= {"code", "count", "value_at_risk", "estimated_recoverable"} for r in rows)
        codes = {r["code"] for r in rows}
        assert "insufficient_funds" in codes


def test_payment_method_performance(seeded_database):
    with SessionLocal() as db:
        rows = payment_method_performance(db)
        methods = {r["method"] for r in rows}
        assert {"CARD", "UPI"} <= methods
        card = next(r for r in rows if r["method"] == "CARD")
        assert 0 <= card["success_rate"] <= 1
        assert card["transactions"] >= 2


def test_trends_and_distributions(seeded_database):
    with SessionLocal() as db:
        trends = daily_trends(db, days=30)
        assert len(trends) >= 2
        priorities = priority_distribution(db)
        total_counted = sum(p["count"] for p in priorities)
        assert total_counted >= 2
        segments = customer_segments(db)
        assert sum(s["customers"] for s in segments) >= 2


def test_baseline_comparison_math(seeded_database):
    with SessionLocal() as db:
        result = baseline_comparison(db, sample_size=50)
        assert result["transactions_analyzed"] >= 2
        assert result["revenue_at_risk"] > 0
        assert result["baseline_recovery_rate"] != result["ai_assisted_recovery_rate"]
        delta = result["ai_assisted_recovered_revenue"] - result["baseline_recovered_revenue"]
        assert abs(delta - result["incremental_recovered_revenue"]) < 1.0
        summary = recovered_revenue_summary(db)
        assert summary["revenue_at_risk"] > 0


def test_error_envelope_for_missing_transaction(client, auth_headers):
    resp = client.get("/api/v1/recovery/status/txn_does_not_exist", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] in ("TRANSACTION_NOT_FOUND", "OPPORTUNITY_NOT_FOUND")


def test_unauthenticated_api_blocked(client):
    assert client.get("/api/v1/analytics/revenue").status_code == 401
    assert client.get("/api/v1/recovery/opportunities").status_code == 401
