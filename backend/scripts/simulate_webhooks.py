"""Webhook simulator.

    # POST events to a running API (signature-signed):
    python scripts/simulate_webhooks.py --url http://localhost:8000 --count 50

    # Or ingest directly into the DB (no server needed):
    python scripts/simulate_webhooks.py --mode db --count 50
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

METHODS = [("UPI", 0.42), ("CARD", 0.34), ("NETBANKING", 0.14), ("WALLET", 0.10)]
FAILURE_CODES_BY_METHOD: dict[str, list[tuple[str, float]]] = {
    "CARD": [
        ("insufficient_funds", 0.28), ("expired_card", 0.18), ("suspected_fraud", 0.08),
        ("invalid_card", 0.14), ("bank_timeout", 0.18), ("payment_method_declined", 0.14),
    ],
    "UPI": [
        ("network_error", 0.32), ("temporary_failure", 0.24), ("insufficient_funds", 0.24),
        ("payment_method_declined", 0.20),
    ],
    "NETBANKING": [("bank_timeout", 0.36), ("temporary_failure", 0.28), ("network_error", 0.20), ("gateway_error", 0.16)],
    "WALLET": [("insufficient_funds", 0.40), ("network_error", 0.28), ("payment_method_declined", 0.32)],
}


def build_event(rng: random.Random, index: int, existing_customer_ids: list[str]) -> dict:
    method = rng.choices([m for m, _ in METHODS], weights=[w for _, w in METHODS])[0]
    code = rng.choices([c for c, _ in FAILURE_CODES_BY_METHOD[method]], weights=[w for _, w in FAILURE_CODES_BY_METHOD[method]])[0]
    status = "ABANDONED" if rng.random() < 0.12 else "FAILED"
    return {
        "event_id": f"evt_sim_{uuid.uuid4().hex[:12]}",
        "transaction_id": f"txn_sim_{index:05d}_{uuid.uuid4().hex[:6]}",
        "customer_id": rng.choice(existing_customer_ids),
        "amount": round(min(max(rng.lognormvariate(7.6, 1.1), 99), 200_000), 2),
        "currency": "INR",
        "payment_method": method,
        "payment_provider": rng.choice(["razorpay", "stripe", "adyen"]),
        "status": status,
        "failure_code": None if status == "ABANDONED" else code,
        "failure_reason": None,
        "attempt_number": rng.choices([1, 2, 3], weights=[60, 27, 13])[0],
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=rng.uniform(0, 120))).isoformat(),
    }


def existing_customers() -> list[str]:
    from app.core.database import SessionLocal
    from app.models import Customer

    with SessionLocal() as db:
        return [row[0] for row in db.query(Customer.external_customer_id).all()] or ["cus_walkin"]


def post_mode(url: str, count: int, secret: str | None = None) -> None:
    import httpx

    from app.core.config import settings

    secret = secret or settings.webhook_secret
    rng = random.Random(2026)
    customer_ids = existing_customers()
    ok = dup = err = 0
    started = time.time()
    with httpx.Client(timeout=30.0) as client:
        for i in range(count):
            event = build_event(rng, i, customer_ids)
            body = json.dumps(event).encode()
            resp = client.post(
                f"{url.rstrip('/')}/api/v1/webhook/payment-failed",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
                },
                params={"sync": "false"},
            )
            if resp.status_code == 202:
                if resp.json().get("duplicate"):
                    dup += 1
                else:
                    ok += 1
            elif resp.status_code == 422:
                err += 1
                print(f"validation rejected: {resp.text[:160]}")
            else:
                err += 1
    from app.workers.webhook_worker import _queue

    try:
        _queue.join()
    except Exception:
        time.sleep(2)
    print(f"Posted {count} webhooks in {time.time() - started:.1f}s -> accepted={ok} duplicate={dup} rejected={err}")


def db_mode(count: int) -> None:
    from app.core.database import SessionLocal
    from app.schemas.webhook import PaymentEventIn
    from app.services.webhook_service import ingest_payment_event

    rng = random.Random(2026)
    customer_ids = existing_customers()
    created = 0
    started = time.time()
    with SessionLocal() as db:
        for i in range(count):
            result = ingest_payment_event(db, PaymentEventIn.model_validate(build_event(rng, i, customer_ids)))
            created += 0 if result["duplicate"] else 1
    print(f"Ingested {created}/{count} new webhooks directly in {time.time() - started:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate payment-provider failure webhooks")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--mode", choices=["http", "db"], default="http")
    parser.add_argument(
        "--secret",
        default=None,
        help="Webhook signing secret (defaults to local WEBHOOK_SECRET; set this for a hosted API)",
    )
    args = parser.parse_args()

    if args.mode == "db":
        db_mode(args.count)
    else:
        post_mode(args.url, args.count, secret=args.secret)


if __name__ == "__main__":
    main()
