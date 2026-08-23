"""Agent tool + orchestrator tests: numbers must come from the database."""
from __future__ import annotations

from app.agents.intent import classify_intent, extract_customer_id, extract_method
from app.core.database import SessionLocal
from app.analytics.metrics import revenue_metrics


def _db():
    return SessionLocal()


def test_intent_classification():
    assert classify_intent("How much revenue can we potentially recover?") == "RECOVERABLE_REVENUE"
    assert classify_intent("Show me the top 10 recovery opportunities") == "TOP_OPPORTUNITIES"
    assert classify_intent("Why did payment failures increase this week?") in ("FAILURE_REASONS", "WEEK_COMPARISON")
    assert classify_intent("Which customers should I prioritize today?") == "CUSTOMER_PRIORITIZATION"
    assert extract_customer_id("analyze customer cus_9001 please") == "cus_9001"
    assert extract_method("is UPI causing losses?") == "UPI"


def test_revenue_metrics_tool_returns_db_numbers(seeded_database):
    with _db() as db:
        from app.agents.tools import get_revenue_metrics

        data = get_revenue_metrics(db, days=30)
        direct = revenue_metrics(db, days=30)
        assert data["revenue_at_risk"] == direct["revenue_at_risk"]
        assert data["revenue_at_risk"] > 0


def test_recovery_opportunities_tool_sorted_by_expected_value(seeded_database):
    with _db() as db:
        from app.agents.tools import get_recovery_opportunities

        opps = get_recovery_opportunities(db, limit=10)
        values = [o["expected_recovery_value"] for o in opps]
        assert values == sorted(values, reverse=True)
        assert all(set(o) >= {"customer_name", "amount_at_risk", "recovery_probability", "priority"} for o in opps)


def test_customer_analysis_tool(seeded_database):
    with _db() as db:
        from app.agents.tools import analyze_customer

        result = analyze_customer(db, customer_id="cus_9001")
        assert result is not None
        assert result["customer"]["lifetime_value"] == 200_000.0
        assert result["customer"]["successful_transactions"] == 12
        assert any(m["method"] == "CARD" for m in result["payment_methods"])
        assert analyze_customer(db, customer_id="cus_missing") is None


def test_calculate_recovery_value_formula(seeded_database):
    with _db() as db:
        from app.agents.tools import calculate_recovery_value

        data = calculate_recovery_value(db)
        assert data is not None
        expected = round(data["revenue_at_risk"] * data["recovery_probability"], 2)
        assert abs(data["expected_recovery_value"] - expected) < 0.01
        assert "x" in data["formula"]


def test_chat_endpoint_answers_with_metrics(client, auth_headers):
    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "Which customers should I prioritize today?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intent"] == "CUSTOMER_PRIORITIZATION"
    assert "get_recovery_opportunities" in body["tools_used"]
    assert len(body["answer"]) > 40
    assert isinstance(body["recommendations"], list) and body["recommendations"]
    # answer text must contain at least one rupee figure derived from DB data
    assert "\u20b9" in body["answer"] or body["metrics"]


def test_chat_requires_auth(client):
    resp = client.post("/api/v1/ai/chat", json={"message": "how much revenue at risk?"})
    assert resp.status_code == 401
