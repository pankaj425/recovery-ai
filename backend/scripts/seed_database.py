"""One-command database seeder.

    python scripts/seed_database.py              # fresh dataset (drops tables)
    python scripts/seed_database.py --keep       # keep existing data

Steps: create schema -> demo user -> synthetic dataset (incl. 5 showcase
scenarios) -> train ML model -> backfill recovery opportunities for every
failed/abandoned transaction -> print summary KPIs.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Customer, PaymentAttempt, RecoveryOpportunity, Transaction  # noqa: E402
from app.services.auth_service import ensure_demo_user  # noqa: E402

from scripts.generate_dataset import SCENARIOS, build_scenario_rows, finalize_customer_aggregates, generate_customers, generate_transactions  # noqa: E402


def reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()


def _insert_customers(session, customers: list[dict], chunk: int = 1000) -> dict[str, Customer]:
    by_ext: dict[str, Customer] = {}
    for i in range(0, len(customers), chunk):
        objs = [Customer(**c) for c in customers[i : i + chunk]]
        session.add_all(objs)
        session.flush()
        for obj in objs:
            by_ext[obj.external_customer_id] = obj
    session.commit()
    return by_ext


def _insert_transactions(session, transactions: list[dict], cust_by_ext: dict[str, Customer], chunk: int = 2000) -> dict[str, Transaction]:
    by_str: dict[str, Transaction] = {}
    for i in range(0, len(transactions), chunk):
        objs = []
        for t in transactions[i : i + chunk]:
            row = {k: v for k, v in t.items() if not k.startswith("_")}
            row["customer_id"] = cust_by_ext[t["_customer_external_id"]].id
            objs.append(Transaction(**row))
        session.add_all(objs)
        session.commit()
        for obj in objs:
            by_str[obj.transaction_id] = obj
    return by_str


def _insert_attempts(session, attempts: list[dict], txn_by_str: dict[str, Transaction], chunk: int = 4000) -> None:
    for i in range(0, len(attempts), chunk):
        objs = [
            PaymentAttempt(
                **{k: v for k, v in a.items() if not k.startswith("_")},
                transaction_id=txn_by_str[a["_transaction_id_str"]].id,
            )
            for a in attempts[i : i + chunk]
        ]
        session.add_all(objs)
        session.commit()


def backfill_opportunities(session) -> int:
    from app.services.opportunity_pipeline import PipelineCache, run_recovery_pipeline

    failed_ids = [row[0] for row in session.query(Transaction.id).filter(Transaction.status.in_(("FAILED", "ABANDONED"))).all()]
    cache = PipelineCache.build(session)
    total = 0
    for txn_id in failed_ids:
        run_recovery_pipeline(session, session.get(Transaction, txn_id), cache)
        total += 1
        if total % 250 == 0:
            session.commit()
            print(f"  scored {total}/{len(failed_ids)}", end="\r", flush=True)
            cache = PipelineCache.build(session)
    session.commit()
    print(" " * 40, end="\r")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the RecoveryAI database")
    parser.add_argument("--customers", type=int, default=5000)
    parser.add_argument("--transactions", type=int, default=20000)
    parser.add_argument("--keep", action="store_true", help="do not drop existing tables")
    args = parser.parse_args()

    started = time.time()
    if not args.keep:
        reset_schema()
    else:
        init_db()

    customers = generate_customers(args.customers)
    transactions, attempts = generate_transactions(customers, count=args.transactions)

    scenario_txns, scenario_attempts = build_scenario_rows(start_txn_number=len(transactions) + 1)
    known_ids = {c["external_customer_id"] for c in customers}
    for scenario in SCENARIOS:
        if scenario["external_customer_id"] not in known_ids:
            name = scenario["name"]
            customers.append(
                {
                    "external_customer_id": scenario["external_customer_id"],
                    "name": name,
                    "email": f"{name.lower().replace(' ', '.')}@example.com",
                    "segment": None,
                    "total_spend": 0.0,
                    "lifetime_value": 0.0,
                    "successful_transactions": 0,
                    "failed_transactions": 0,
                }
            )
    transactions.extend(scenario_txns)
    attempts.extend(scenario_attempts)
    finalize_customer_aggregates(customers, transactions)

    with SessionLocal() as session:
        ensure_demo_user(session)
        cust_by_ext = _insert_customers(session, customers)
        txn_by_str = _insert_transactions(session, transactions, cust_by_ext)
        _insert_attempts(session, attempts, txn_by_str)

        from app.ml.model_registry import RecoveryProbabilityModel, train_model

        print("Training recovery-probability model...")
        RecoveryProbabilityModel.reset(persist_new=train_model())

        scored = backfill_opportunities(session)

        kpis = {
            "customers": session.query(Customer).count(),
            "transactions": session.query(Transaction).count(),
            "payment_attempts": session.query(PaymentAttempt).count(),
            "opportunities": session.query(RecoveryOpportunity).count(),
        }

    print(f"\nSeed complete in {time.time() - started:.1f}s")
    for key, value in kpis.items():
        print(f"  {key:>18}: {value:,}")
    print(f"  {'opps_scored':>18}: {scored:,}")

    scenario_ids = [s["external_customer_id"] for s in SCENARIOS]
    with SessionLocal() as session:
        print("\nShowcase scenarios:")
        rows = (
            session.query(RecoveryOpportunity, Transaction, Customer)
            .join(Transaction, RecoveryOpportunity.transaction_id == Transaction.id)
            .join(Customer, RecoveryOpportunity.customer_id == Customer.id)
            .filter(Customer.external_customer_id.in_(scenario_ids))
            .order_by(RecoveryOpportunity.recovery_score.desc())
            .all()
        )
        for opp, txn, customer in rows:
            print(
                f"  [{opp.priority:^8}] {txn.transaction_id} {customer.name:<14} "
                f"\u20b9{opp.revenue_at_risk:>10,.0f} p={opp.recovery_probability:.2f} "
                f"exp=\u20b9{opp.expected_recovery_value:>9,.0f} score={opp.recovery_score:.1f}"
            )


if __name__ == "__main__":
    main()
