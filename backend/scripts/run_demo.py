"""End-to-end recovery simulation (Section 26).

Cohort: the top 100 open recovery opportunities by expected value.
Compares the rule-based dunning baseline against RecoveryAI's model-guided
strategy. Every printed number is computed from live database state.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.analytics.baseline import baseline_comparison  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.utils.formatting import inr, pct  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="RecoveryAI demo simulation")
    parser.add_argument("--cohort", type=int, default=100)
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        result = baseline_comparison(db, sample_size=args.cohort)

    line = "=" * 44
    print(line)
    print("RECOVERYAI DEMO RESULTS")
    print(line)
    print(f"\nTransactions analyzed: {result['transactions_analyzed']}\n")
    print(f"Revenue at risk: {inr(result['revenue_at_risk'])}\n")
    print(f"Baseline recovery rate: {pct(result['baseline_recovery_rate'])}")
    print(f"AI-assisted recovery rate: {pct(result['ai_assisted_recovery_rate'])}\n")
    print(f"Baseline recovered revenue: {inr(result['baseline_recovered_revenue'])}")
    print(f"AI-assisted recovered revenue: {inr(result['ai_assisted_recovered_revenue'])}")
    print(f"Incremental recovered revenue: {inr(result['incremental_recovered_revenue'])}")
    print(f"Recovery improvement: +{result['recovery_improvement_pct']:.1f}%\n")
    print(f"Unnecessary baseline retries avoided: {result['unnecessary_baseline_retries']}")
    print(f"High-value opportunities captured: {result['high_value_opportunities_captured']} "
          f"({inr(result['high_value_expected_recovery'])} expected)\n")
    print(line)


if __name__ == "__main__":
    main()
