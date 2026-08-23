"""Minimal dependency-free logistic regression with L2 regularization.

Chosen intentionally: transparent coefficients, deterministic training,
trivially auditable inference - suitable for a financial baseline model.
"""
from __future__ import annotations

import math


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


class LogisticRegression:
    def __init__(self, learning_rate: float = 0.15, epochs: int = 400, l2: float = 0.01) -> None:
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2 = l2
        self.weights: list[float] = []
        self.bias: float = 0.0
        self.means: list[float] = []
        self.stds: list[float] = []

    # ------------------------------------------------------------------ #
    def fit(self, X: list[list[float]], y: list[int]) -> "LogisticRegression":
        if not X or len(X) != len(y):
            raise ValueError("X and y must be non-empty and aligned")
        n_samples, n_features = len(X), len(X[0])

        self.means = [sum(row[j] for row in X) / n_samples for j in range(n_features)]
        variances = [
            sum((row[j] - self.means[j]) ** 2 for row in X) / n_samples for j in range(n_features)
        ]
        self.stds = [math.sqrt(v) or 1.0 for v in variances]

        Xs = [self._standardize(row) for row in X]
        self.weights = [0.0] * n_features
        self.bias = 0.0

        for _ in range(self.epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for row, label in zip(Xs, y):
                p = _sigmoid(sum(w * x for w, x in zip(self.weights, row)) + self.bias)
                err = p - label
                for j in range(n_features):
                    grad_w[j] += err * row[j]
                grad_b += err
            for j in range(n_features):
                grad_w[j] = grad_w[j] / n_samples + self.l2 * self.weights[j]
                self.weights[j] -= self.learning_rate * grad_w[j]
            self.bias -= self.learning_rate * (grad_b / n_samples)
        return self

    def predict_proba(self, features: list[float]) -> float:
        xs = self._standardize(features)
        return _sigmoid(sum(w * x for w, x in zip(self.weights, xs)) + self.bias)

    # ------------------------------------------------------------------ #
    def contributions(self, features: list[float]) -> list[tuple[str, float]]:
        """Per-feature signed contribution to the log-odds (for explanations)."""
        xs = self._standardize(features)
        return [(name, w * x) for name, w, x in zip(self.feature_names or [], self.weights, xs)]

    feature_names: list[str] | None = None

    def _standardize(self, row: list[float]) -> list[float]:
        return [(x - m) / s for x, m, s in zip(row, self.means, self.stds)]

    # ------------------------- persistence ----------------------------- #
    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "bias": self.bias,
            "means": self.means,
            "stds": self.stds,
            "feature_names": self.feature_names or [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LogisticRegression":
        model = cls()
        model.weights = data["weights"]
        model.bias = data["bias"]
        model.means = data["means"]
        model.stds = data["stds"]
        model.feature_names = data.get("feature_names") or None
        return model
