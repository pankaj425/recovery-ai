"""Synthetic dataset generator - realistic Indian e-commerce payment data.

No real personal or financial data is used anywhere; identities are synthetic.
Deterministic under a fixed RNG seed.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Rohan", "Rahul", "Amit", "Vikram",
    "Neha", "Priya", "Ananya", "Diya", "Kavya", "Meera", "Pooja", "Sneha", "Arjun",
    "Karan", "Siddharth", "Ravi", "Suresh", "Deepak", "Manish", "Varun",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Singh", "Kumar", "Gupta", "Mehta", "Iyer", "Reddy",
    "Nair", "Joshi", "Desai", "Kulkarni", "Chopra", "Malhotra", "Bose", "Das",
    "Kapoor", "Rao", "Shetty",
]

METHOD_WEIGHTS = [("UPI", 0.42), ("CARD", 0.34), ("NETBANKING", 0.14), ("WALLET", 0.10)]
PROVIDERS = ["razorpay", "stripe", "adyen"]
PROVIDER_WEIGHTS = [0.55, 0.30, 0.15]

FAILURE_CODES_BY_METHOD: dict[str, list[tuple[str, float]]] = {
    "CARD": [
        ("insufficient_funds", 0.28),
        ("expired_card", 0.18),
        ("suspected_fraud", 0.10),
        ("risk_rule_false_positive", 0.05),
        ("invalid_card", 0.14),
        ("bank_timeout", 0.13),
        ("payment_method_declined", 0.12),
    ],
    "UPI": [
        ("network_error", 0.30),
        ("temporary_failure", 0.22),
        ("insufficient_funds", 0.24),
        ("payment_method_declined", 0.16),
        ("gateway_error", 0.08),
    ],
    "NETBANKING": [
        ("bank_timeout", 0.34),
        ("temporary_failure", 0.26),
        ("network_error", 0.18),
        ("gateway_error", 0.12),
        ("integration_error", 0.10),
    ],
    "WALLET": [
        ("insufficient_funds", 0.38),
        ("network_error", 0.24),
        ("payment_method_declined", 0.22),
        ("temporary_failure", 0.16),
    ],
}

STATUS_WEIGHTS = [("SUCCESS", 0.72), ("FAILED", 0.18), ("ABANDONED", 0.06), ("PENDING", 0.02), ("REFUNDED", 0.02)]


def _weighted(rng: random.Random, options: list[tuple[str, float]]) -> str:
    return rng.choices([o[0] for o in options], weights=[o[1] for o in options])[0]


def make_customer_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def generate_customers(count: int, *, start_index: int = 1) -> list[dict]:
    """Returns dicts keyed like Customer columns (id assigned later)."""
    rng = random.Random(1000 + count)
    seen_ids: set[str] = set()
    customers: list[dict] = []
    while len(customers) < count:
        external_id = f"cus_{len(seen_ids) + start_index:05d}"
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        name = make_customer_name(rng)
        handle = name.lower().replace(" ", ".")
        customers.append(
            {
                "external_customer_id": external_id,
                "name": name,
                "email": f"{handle}@example.com",
                # filled by finalize_customer_aggregates
                "segment": None,
                "total_spend": 0.0,
                "lifetime_value": 0.0,
                "successful_transactions": 0,
                "failed_transactions": 0,
            }
        )
    return customers


def _make_attempts(
    rng: random.Random,
    *,
    status: str,
    method: str,
    base_time: datetime,
) -> tuple[int, list[dict], str | None]:
    """Builds attempt rows for one transaction. Returns (count, rows, first_failure_code)."""
    rows: list[dict] = []
    failure_code: str | None = None

    if status == "SUCCESS":
        early_failures = rng.choices([0, 1, 2, 3], weights=[62, 24, 10, 4])[0]
        total = early_failures + 1
        for i in range(1, total + 1):
            ts = base_time + timedelta(minutes=rng.randint(1, 6) * i)
            if i <= early_failures:
                code = _weighted(rng, FAILURE_CODES_BY_METHOD[method])
                rows.append(dict(attempt_number=i, payment_method=method, status="FAILED", failure_code=code, timestamp=ts))
            else:
                rows.append(dict(attempt_number=i, payment_method=method, status="SUCCESS", failure_code=None, timestamp=ts))
        return total, rows, None

    if status == "ABANDONED":
        return 1, [dict(attempt_number=1, payment_method=method, status="ABANDONED", failure_code=None, timestamp=base_time)], None

    attempts_total = rng.choices([1, 2, 3, 4], weights=[38, 33, 19, 10])[0]
    for i in range(1, attempts_total + 1):
        code = _weighted(rng, FAILURE_CODES_BY_METHOD[method])
        ts = base_time + timedelta(minutes=rng.randint(2, 45) * i)
        rows.append(
            dict(
                attempt_number=i,
                payment_method=method,
                status="FAILED" if status != "ABANDONED" else "FAILED",
                failure_code=None if status == "ABANDONED" else code,
                timestamp=ts,
            )
        )
        if i == 1:
            failure_code = code
    return attempts_total, rows, failure_code


def generate_transactions(
    customers: list[dict],
    *,
    count: int,
    days_back: int = 90,
    seed_extra: int = 0,
) -> tuple[list[dict], list[dict]]:
    """Generates `count` transactions (+ attempts) spread over `days_back` days."""
    rng = random.Random(7000 + count + seed_extra)
    now = datetime.now(timezone.utc)
    transactions: list[dict] = []
    attempts: list[dict] = []

    for i in range(count):
        cust = customers[rng.randrange(len(customers))]
        amount = round(min(max(rng.lognormvariate(7.6, 1.15), 49), 480_000), 2)
        created = now - timedelta(
            days=rng.uniform(0, days_back),
            minutes=rng.uniform(0, 60 * 24),
        )
        status = _weighted(rng, STATUS_WEIGHTS)
        method = _weighted(rng, METHOD_WEIGHTS)

        attempt_count, attempt_rows, first_code = _make_attempts(
            rng, status=status, method=method, base_time=created
        )
        completed_at = (
            created + timedelta(minutes=rng.randint(1, 8))
            if status == "SUCCESS"
            else None
        )
        txn_row = {
            "transaction_id": f"txn_{i + 1:06d}",
            "_customer_external_id": cust["external_customer_id"],
            "amount": amount,
            "currency": "INR",
            "status": status,
            "payment_method": method,
            "payment_provider": _weighted(rng, list(zip(PROVIDERS, PROVIDER_WEIGHTS))),
            "failure_code": first_code if status in ("FAILED",) else None,
            "failure_reason": None,
            "attempt_count": attempt_count,
            "created_at": created,
            "completed_at": completed_at,
        }
        transactions.append(txn_row)
        for row in attempt_rows:
            row["_transaction_id_str"] = txn_row["transaction_id"]
        attempts.extend(attempt_rows)

    return transactions, attempts


# --------------------------------------------------------------------------- #
# Demo scenarios (Section 23). Created fresh, timestamps inside the last 36h
# so recency scoring keeps them at the top of the queue.
# --------------------------------------------------------------------------- #
SCENARIOS: list[dict] = [
    {
        "key": "FRAUD_FALSE_POSITIVE",
        "external_customer_id": "cus_rahul01",
        "name": "Rahul Sharma",
        "amount": 50_000.0,
        "method": "CARD",
        "status": "FAILED",
        "failure_code": "risk_rule_false_positive",
        "attempts": 2,
        "history_successes": 14,
        "history_spend": 420_000.0,
        "expected_priority": "CRITICAL",
    },
    {
        "key": "REPEATED_FAILURE_HIGH_VALUE",
        "external_customer_id": "cus_amit01",
        "name": "Amit Kumar",
        "amount": 25_000.0,
        "method": "CARD",
        "status": "FAILED",
        "failure_code": "insufficient_funds",
        "attempts": 3,
        "history_successes": 11,
        "history_spend": 180_000.0,
        "expected_priority": "HIGH",
    },
    {
        "key": "EXPIRED_CARD",
        "external_customer_id": "cus_priya01",
        "name": "Priya Patel",
        "amount": 12_000.0,
        "method": "CARD",
        "status": "FAILED",
        "failure_code": "expired_card",
        "attempts": 1,
        "history_successes": 9,
        "history_spend": 96_000.0,
        "expected_priority": "HIGH",
    },
    {
        "key": "INSUFFICIENT_FUNDS_LOW_VALUE",
        "external_customer_id": "cus_neha01",
        "name": "Neha Singh",
        "amount": 8_000.0,
        "method": "UPI",
        "status": "FAILED",
        "failure_code": "insufficient_funds",
        "attempts": 2,
        "history_successes": 3,
        "history_spend": 18_000.0,
        "expected_priority": "MEDIUM",
    },
    {
        "key": "ABANDONED_CART",
        "external_customer_id": "cus_vikram01",
        "name": "Vikram Mehta",
        "amount": 15_000.0,
        "method": "UPI",
        "status": "ABANDONED",
        "failure_code": None,
        "attempts": 1,
        "history_successes": 7,
        "history_spend": 88_000.0,
        "expected_priority": "HIGH",
    },
]


def build_scenario_rows(start_txn_number: int, hours_back: float = 14.0) -> tuple[list[dict], list[dict]]:
    """Creates the five showcase scenarios with rich history + recent failures.

    Returns (extra_transactions, extra_attempts); history txns included.
    """
    rng = random.Random(4242)
    now = datetime.now(timezone.utc)
    txns: list[dict] = []
    attempts: list[dict] = []
    txn_no = start_txn_number

    for scenario in SCENARIOS:
        cust_ext = scenario["external_customer_id"]
        # --- historical successful transactions ------------------------- #
        hist_count = max(scenario["history_successes"], 5)
        for h in range(hist_count):
            created = now - timedelta(days=90 - h * int(85 / hist_count), minutes=rng.uniform(0, 600))
            amount = round(scenario["history_spend"] / hist_count * rng.uniform(0.6, 1.5), 2)
            method = scenario["method"] if rng.random() < 0.7 else _weighted(rng, METHOD_WEIGHTS)
            tid = f"txn_{txn_no:06d}"
            txn_no += 1
            txns.append(
                {
                    "transaction_id": tid,
                    "_customer_external_id": cust_ext,
                    "amount": amount,
                    "currency": "INR",
                    "status": "SUCCESS",
                    "payment_method": method,
                    "payment_provider": "razorpay",
                    "failure_code": None,
                    "failure_reason": None,
                    "attempt_count": 1,
                    "created_at": created,
                    "completed_at": created + timedelta(minutes=2),
                }
            )

        # --- the showcase failing transaction --------------------------- #
        created = now - timedelta(hours=hours_back * rng.uniform(0.4, 1.0))
        tid = f"txn_{txn_no:06d}"
        txn_no += 1
        attempt_count = scenario["attempts"] if scenario["status"] == "FAILED" else 1
        txns.append(
            {
                "transaction_id": tid,
                "_customer_external_id": cust_ext,
                "amount": scenario["amount"],
                "currency": "INR",
                "status": scenario["status"],
                "payment_method": scenario["method"],
                "payment_provider": "razorpay",
                "failure_code": scenario["failure_code"],
                "failure_reason": None,
                "attempt_count": attempt_count,
                "created_at": created,
                "completed_at": None,
            }
        )
        for a in range(1, attempt_count + 1):
            last = a == attempt_count
            attempts.append(
                {
                    "_transaction_id_str": tid,
                    "attempt_number": a,
                    "payment_method": scenario["method"],
                    "status": scenario["status"] if last else "FAILED",
                    "failure_code": scenario["failure_code"],
                    "timestamp": created + timedelta(minutes=9 * a),
                }
            )

    return txns, attempts


def finalize_customer_aggregates(customers: list[dict], transactions: Iterable[dict]) -> None:
    """Compute spend/LTV/counters/segments in-memory before DB insertion."""
    stats: dict[str, dict] = {}
    for t in transactions:
        s = stats.setdefault(t["_customer_external_id"], {"success": 0, "failed": 0, "spend": 0.0, "refunded": 0.0})
        if t["status"] == "SUCCESS":
            s["success"] += 1
            s["spend"] += t["amount"]
        elif t["status"] == "REFUNDED":
            s["refunded"] += t["amount"]
        elif t["status"] in ("FAILED", "ABANDONED"):
            s["failed"] += 1

    for c in customers:
        s = stats.get(c["external_customer_id"], {"success": 0, "failed": 0, "spend": 0.0, "refunded": 0.0})
        c["successful_transactions"] = s["success"]
        c["failed_transactions"] = s["failed"]
        c["total_spend"] = round(s["spend"] - s["refunded"], 2)
        c["lifetime_value"] = round(max((s["spend"] - s["refunded"]) * 1.15, s["spend"]), 2)
        if s["success"] >= 20 and c["total_spend"] >= 100_000:
            c["segment"] = "HIGH"
        elif s["success"] >= 5 and c["total_spend"] >= 20_000:
            c["segment"] = "MEDIUM"
        else:
            c["segment"] = "LOW"
