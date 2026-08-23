"""Model registry: trains (deterministically), persists and serves the
recovery-probability model.

Training data is generated from a documented latent ground-truth function
that encodes domain priors (strong history -> higher recovery, more failed
attempts -> lower, etc.) with sampling noise. For the hackathon this stands
in for historical recovery outcomes; the training entry point stays identical
for real labeled data.
"""
from __future__ import annotations

import json
import math
import random
import threading
from pathlib import Path
from typing import NamedTuple

from app.ml.features import FEATURE_NAMES, RecoveryFeatures
from app.ml.logistic import LogisticRegression

MODEL_VERSION = "logreg-v1"
ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "recovery_model.json"

_TRAINING_SEED = 42
_TRAINING_SAMPLES = 6000

# Latent ground truth: log-odds weights over roughly normalized features.
# Calibrated so that: strong-history fraud false-positives ~ 0.85-0.92,
# repeated failures with good history ~ 0.55-0.70, weak history ~ 0.40-0.55.
_LATENT_BIAS = -2.3
_LATENT_WEIGHTS: dict[str, float] = {
    "log_amount": 0.12,
    "attempt_pressure": -1.8,
    "log_ltv": 0.50,
    "customer_success_rate": 1.5,
    "method_success_rate": 1.0,
    "cause_prior": 1.4,
    "recency_factor": 0.7,
    "txn_frequency": 0.30,
}

_FEATURE_SCALERS = [5.0, 1.0, 5.5, 1.0, 1.0, 1.0, 1.0, 1.0]


class TrainingSample(NamedTuple):
    vector: list[float]
    label: int


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _latent_probability(vector: list[float]) -> float:
    scaled = [v / s for v, s in zip(vector, _FEATURE_SCALERS)]
    z = _LATENT_BIAS + sum(w * v for w, v in zip(_LATENT_WEIGHTS.values(), scaled))
    return _sigmoid(z)


def _sample_training_point(rng: random.Random) -> TrainingSample:
    feats = RecoveryFeatures(
        amount=min(max(rng.lognormvariate(7.6, 1.1), 50), 500_000),
        attempt_count=rng.choices([1, 2, 3, 4], weights=[55, 25, 13, 7])[0],
        lifetime_value=min(max(rng.lognormvariate(9.2, 1.3), 0), 1_500_000),
        customer_successes=int(rng.random() ** 1.5 * 40),
        customer_failures=int(rng.random() * 10),
        method_success_rate=max(0.05, min(0.95, rng.gauss(0.72, 0.16))),
        cause_prior=rng.uniform(0.28, 0.72),
        hours_since_failure=rng.expovariate(1 / 48),
        txn_frequency_per_month=rng.expovariate(1 / 6),
    )
    vector = feats.to_vector()
    label = 1 if rng.random() < _latent_probability(vector) else 0
    return TrainingSample(vector=vector, label=label)


def train_model(samples: int = _TRAINING_SAMPLES) -> LogisticRegression:
    rng = random.Random(_TRAINING_SEED)
    points = [_sample_training_point(rng) for _ in range(samples)]
    model = LogisticRegression(learning_rate=0.25, epochs=500, l2=0.012)
    model.fit([p.vector for p in points], [p.label for p in points])
    model.feature_names = list(FEATURE_NAMES)
    return model


def save_model(model: LogisticRegression, path: Path = ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": MODEL_VERSION, "model": model.to_dict()}
    path.write_text(json.dumps(payload))


def load_model(path: Path = ARTIFACT_PATH) -> LogisticRegression | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        model = LogisticRegression.from_dict(payload["model"])
        model.feature_names = payload["model"].get("feature_names") or list(FEATURE_NAMES)
        return model
    except (json.JSONDecodeError, KeyError, OSError):
        return None


class PredictionResult(NamedTuple):
    probability: float
    confidence: float
    model_version: str
    factors: list[tuple[str, float]]

    def to_dict(self) -> dict:
        return {
            "recovery_probability": round(self.probability, 4),
            "confidence": round(self.confidence, 4),
            "model_version": self.model_version,
            "top_factors": [
                {"feature": name, "contribution_log_odds": round(val, 3)} for name, val in self.factors
            ],
        }


class RecoveryProbabilityModel:
    """Thread-safe singleton serving predictions."""

    _lock = threading.Lock()
    _instance: "RecoveryProbabilityModel | None" = None

    def __init__(self, model: LogisticRegression) -> None:
        self._model = model

    @classmethod
    def get(cls) -> "RecoveryProbabilityModel":
        with cls._lock:
            if cls._instance is None:
                loaded = load_model()
                if loaded is None:
                    loaded = train_model()
                    save_model(loaded)
                cls._instance = cls(loaded)
            return cls._instance

    @classmethod
    def reset(cls, persist_new: LogisticRegression | None = None) -> None:
        with cls._lock:
            if persist_new is not None:
                save_model(persist_new)
            cls._instance = None

    def predict(self, features: RecoveryFeatures) -> PredictionResult:
        vector = features.to_vector()
        probability = self._model.predict_proba(vector)

        standardized = [
            (x - m) / s for x, m, s in zip(vector, self._model.means, self._model.stds)
        ]
        contributions = (
            (name, w * x)
            for name, w, x in zip(model_feature_names(self._model), self._model.weights, standardized)
        )
        top_factors = sorted(contributions, key=lambda t: abs(t[1]), reverse=True)[:4]

        confidence = max(0.5, min(0.95, 0.55 + abs(probability - 0.5) * 0.9))
        return PredictionResult(
            probability=probability,
            confidence=confidence,
            model_version=MODEL_VERSION,
            factors=top_factors,
        )


def model_feature_names(model: LogisticRegression) -> list[str]:
    return model.feature_names or list(FEATURE_NAMES)


def build_features_from_context(
    *,
    amount: float,
    attempt_count: int,
    lifetime_value: float,
    customer_successes: int,
    customer_failures: int,
    method_success_rate: float,
    cause_prior: float,
    hours_since_failure: float,
    txn_frequency_per_month: float,
) -> RecoveryFeatures:
    """Single construction point used by services so feature semantics stay consistent."""
    return RecoveryFeatures(
        amount=amount,
        attempt_count=attempt_count,
        lifetime_value=lifetime_value,
        customer_successes=customer_successes,
        customer_failures=customer_failures,
        method_success_rate=method_success_rate,
        cause_prior=cause_prior,
        hours_since_failure=max(hours_since_failure, 0.0),
        txn_frequency_per_month=txn_frequency_per_month,
    )
