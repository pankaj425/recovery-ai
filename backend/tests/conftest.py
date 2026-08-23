"""Pytest fixtures: isolated SQLite DB, seeded mini-dataset, authed API client."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_recovery_ai.db")
os.environ.setdefault("LLM_PROVIDER", "mock")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Customer, PaymentAttempt, Transaction  # noqa: E402
from app.services.auth_service import ensure_demo_user  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        db_file = Path("test_recovery_ai.db")
        if db_file.exists():
            db_file.unlink()
    except PermissionError:
        pass  # Windows keeps the file mapped briefly; safe to leave for cleanup


def _seed_mini_dataset() -> None:
    with SessionLocal() as db:
        ensure_demo_user(db)
        c1 = Customer(
            external_customer_id="cus_9001",
            name="Rahul Sharma",
            email="rahul@example.com",
            segment="HIGH",
            total_spend=180_000.0,
            lifetime_value=200_000.0,
            successful_transactions=12,
            failed_transactions=1,
        )
        c2 = Customer(
            external_customer_id="cus_9002",
            name="Neha Singh",
            email="neha@example.com",
            segment="LOW",
            total_spend=4_000.0,
            lifetime_value=5_000.0,
            successful_transactions=1,
            failed_transactions=3,
        )
        db.add_all([c1, c2])
        db.flush()

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        failed_txn = Transaction(
            transaction_id="txn_fail_001",
            customer_id=c1.id,
            amount=25_000.0,
            currency="INR",
            status="FAILED",
            payment_method="CARD",
            payment_provider="razorpay",
            failure_code="insufficient_funds",
            failure_reason=None,
            attempt_count=3,
            created_at=now - timedelta(hours=5),
        )
        abandoned = Transaction(
            transaction_id="txn_abandon_001",
            customer_id=c2.id,
            amount=8_000.0,
            currency="INR",
            status="ABANDONED",
            payment_method="UPI",
            payment_provider="razorpay",
            attempt_count=1,
            created_at=now - timedelta(hours=10),
        )
        success = Transaction(
            transaction_id="txn_ok_001",
            customer_id=c1.id,
            amount=12_000.0,
            currency="INR",
            status="SUCCESS",
            payment_method="CARD",
            payment_provider="razorpay",
            attempt_count=1,
            created_at=now - timedelta(days=2),
            completed_at=now - timedelta(days=2) + timedelta(minutes=2),
        )
        db.add_all([failed_txn, abandoned, success])
        db.flush()
        db.add_all(
            [
                PaymentAttempt(
                    transaction_id=failed_txn.id,
                    attempt_number=i + 1,
                    payment_method="CARD",
                    status="FAILED" if i < 2 else "FAILED",
                    failure_code="insufficient_funds",
                    timestamp=failed_txn.created_at + timedelta(minutes=10 * (i + 1)),
                )
                for i in range(3)
            ]
        )
        db.commit()


@pytest.fixture(scope="session")
def seeded_database(_database):
    from app.ml.model_registry import RecoveryProbabilityModel, train_model

    RecoveryProbabilityModel.reset(persist_new=train_model())
    _seed_mini_dataset()
    with SessionLocal() as db:
        from app.services.opportunity_pipeline import PipelineCache, run_recovery_pipeline

        cache = PipelineCache.build(db)
        for txn in db.query(Transaction).filter(Transaction.status.in_(("FAILED", "ABANDONED"))).all():
            run_recovery_pipeline(db, txn, cache)
        db.commit()
    yield


@pytest.fixture
def client(seeded_database):
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "merchant@recovery.ai", "password": "demo1234"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
