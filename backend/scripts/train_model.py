"""Standalone ML training entry point.

    python scripts/train_model.py [--samples 6000] [--report]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.features import FEATURE_NAMES  # noqa: E402
from app.ml.model_registry import RecoveryProbabilityModel, _sample_training_point, save_model, train_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the recovery-probability model")
    parser.add_argument("--samples", type=int, default=6000)
    args = parser.parse_args()

    model = train_model(samples=args.samples)
    save_model(model)
    RecoveryProbabilityModel.reset()

    print(f"Trained on {args.samples} samples; artifact saved.")
    print(f"Coefficients ({len(FEATURE_NAMES)} features, standardized):")
    for name, weight in zip(model.feature_names or FEATURE_NAMES, model.weights):
        print(f"  {name:<24} {weight:+.4f}")
    print(f"  {'bias':<24} {model.bias:+.4f}")

    # Quick sanity check on one held-out-style synthetic point.
    rng = random.Random(7)
    point = _sample_training_point(rng)

    from app.ml.features import RecoveryFeatures

    probe = RecoveryFeatures(
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
    _ = point
    prediction = RecoveryProbabilityModel.get().predict(probe)
    print("\nSanity probe (25k repeated failure, strong history):")
    print(f"  recovery_probability={prediction.probability:.3f} confidence={prediction.confidence:.2f}")
    print("Model artifact is deterministic under the fixed seed.")


if __name__ == "__main__":
    main()
