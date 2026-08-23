"""Webhook ingestion tests: idempotency, validation, signature, pipeline side-effects."""
from __future__ import annotations

import hashlib
import hmac
import json

from app.core.config import settings


def _payload(event_id: str, txn_id: str = "txn_hook_001", **overrides) -> dict:
    body = {
        "event_id": event_id,
        "transaction_id": txn_id,
        "customer_id": "cus_9001",
        "amount": 25_000.0,
        "currency": "INR",
        "payment_method": "CARD",
        "payment_provider": "razorpay",
        "status": "FAILED",
        "failure_code": "insufficient_funds",
        "attempt_number": 2,
    }
    body.update(overrides)
    return body


def _post(client, body: dict, signed: bool = True):
    raw = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if signed:
        headers["X-Signature"] = hmac.new(settings.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhook/payment-failed", content=raw, headers=headers)


def test_failed_payment_webhook_creates_opportunity(client, auth_headers):
    resp = _post(client, _payload("evt_test_001"))
    assert resp.status_code == 202, resp.text
    ack = resp.json()
    assert ack["processed"] is True and ack["duplicate"] is False

    status_resp = client.get(
        "/api/v1/recovery/status/txn_hook_001", headers=auth_headers
    )
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["success"] is True
    assert data["revenue_at_risk"] == 25000.0
    assert 0.0 <= data["recovery_probability"] <= 1.0
    expected = round(data["revenue_at_risk"] * data["recovery_probability"], 2)
    assert abs(data["expected_recovery_value"] - expected) < 0.01
    assert data["priority"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert len(data["payment_attempts"]) >= 2


def test_duplicate_webhook_is_idempotent(client):
    first = _post(client, _payload("evt_test_dup", txn_id="txn_hook_dup"))
    second = _post(client, _payload("evt_test_dup", txn_id="txn_hook_dup"))
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


def test_invalid_webhook_rejected(client):
    resp = _post(client, {"event_id": "x", "amount": -5})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_unsigned_webhook_blocked_in_production_mode(client, monkeypatch):
    from app.api.v1.endpoints import webhooks as webhook_module

    monkeypatch.setattr(webhook_module.settings, "allow_unsigned_webhooks", False)
    resp = _post(client, _payload("evt_nosig"), signed=False)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


def test_bad_signature_blocked(client):
    raw = json.dumps(_payload("evt_badsig")).encode()
    resp = client.post(
        "/api/v1/webhook/payment-failed",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": "deadbeef"},
    )
    assert resp.status_code == 401
