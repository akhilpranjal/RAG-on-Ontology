"""Selective-prediction utilities and the fused gate.

Every gate produces one score per question, where a *higher* score means "more
likely answerable". A gate then abstains when the score falls below a threshold.
Because the thresholds are chosen on the dev split at fixed coverage targets,
all gates are compared at *matched coverage* on the test split.

Also provides ``LogisticSelector``, the fused gate: a small L2-regularised
logistic regression over the available signals (LLM judge, ontology coverage,
retrieval similarity). It is fitted with scipy alone so the project keeps a
single dependency set.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from evidence_gate.evaluate import auc_score


def row_answer(row: dict) -> str | None:
    """Answer for a row, accepting both sweep rows and legacy run rows."""
    if "answer" in row:
        return row["answer"]
    judge = row.get("judge") or {}
    return judge.get("answer")


def _clean_pairs(scores: list[float], correct: list) -> list[tuple[float, int]]:
    pairs = []
    for score, label in zip(scores, correct):
        if score is None or math.isnan(float(score)):
            continue
        if isinstance(label, dict):
            label = 1 if row_answer(label) == label["gold"] else 0
        pairs.append((float(score), int(label)))
    return pairs


def risk_coverage_curve(scores: list[float], correct: list[int]) -> list[dict]:
    """Selective accuracy at every achievable coverage level."""
    pairs = sorted(_clean_pairs(scores, correct), key=lambda item: -item[0])
    out = []
    hits = 0
    for i, (_, label) in enumerate(pairs, 1):
        hits += label
        out.append(
            {
                "coverage": round(i / len(pairs), 4),
                "selective_accuracy": round(hits / i, 4),
                "risk": round(1.0 - hits / i, 4),
            }
        )
    return out


def aurc(scores: list[float], correct: list[int]) -> float:
    """Area under the risk-coverage curve (lower is better)."""
    curve = risk_coverage_curve(scores, correct)
    if not curve:
        return float("nan")
    return float(np.mean([point["risk"] for point in curve]))


def threshold_at_coverage(scores: list[float], target: float) -> float:
    """Smallest threshold whose coverage is still >= ``target``."""
    values = sorted(
        (float(s) for s in scores if s is not None and not math.isnan(float(s))),
        reverse=True,
    )
    if not values:
        return float("nan")
    if target >= 1.0:
        return values[-1]
    keep = max(1, math.ceil(target * len(values)))
    keep = min(keep, len(values))
    return values[keep - 1]


def coverage_at_threshold(scores: list[float], tau: float) -> float:
    values = [float(s) for s in scores if s is not None and not math.isnan(float(s))]
    if not values:
        return 0.0
    if math.isnan(tau):
        return 1.0
    return sum(1 for value in values if value >= tau) / len(values)


def selective_metrics(scores: list[float], correct: list[dict], tau: float) -> dict:
    """Accuracy over answered questions, plus coverage, at a fixed threshold."""
    rows = list(zip(scores, correct))
    answered = [
        (score, row)
        for score, row in rows
        if score is not None
        and not math.isnan(float(score))
        and (math.isnan(tau) or float(score) >= tau)
    ]
    if not answered:
        return {
            "coverage": 0.0,
            "n_answered": 0,
            "selective_accuracy": None,
            "correct": 0,
        }
    hits = sum(1 for _, row in answered if row_answer(row) == row["gold"])
    return {
        "coverage": round(len(answered) / len(rows), 4) if rows else 0.0,
        "n_answered": len(answered),
        "selective_accuracy": round(hits / len(answered), 4),
        "correct": hits,
    }


def bootstrap_selective_ci(
    scores: list[float],
    correct: list[dict],
    tau: float,
    n_boot: int = 1000,
    seed: int = 42,
) -> list[float] | None:
    """Paired bootstrap CI for selective accuracy at a fixed threshold."""
    answered = [
        (score, row)
        for score, row in zip(scores, correct)
        if score is not None
        and not math.isnan(float(score))
        and (math.isnan(tau) or float(score) >= tau)
    ]
    if len(answered) < 5:
        return None
    rng = random.Random(seed)
    values = [1.0 if row_answer(row) == row["gold"] else 0.0 for _, row in answered]
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return [
        round(means[int(0.025 * n_boot)], 4),
        round(means[int(0.975 * n_boot) - 1], 4),
    ]


def gate_auc(scores: list[float], correct: list[dict]) -> float | None:
    """AUC of a gate score against per-question correctness."""
    pairs = _clean_pairs(
        scores, [1 if row_answer(row) == row["gold"] else 0 for row in correct]
    )
    if not pairs:
        return None
    value = auc_score([s for s, _ in pairs], [c for _, c in pairs])
    return None if math.isnan(value) else round(float(value), 4)


@dataclass
class LogisticSelector:
    """L2-regularised logistic regression with median imputation."""

    feature_names: list[str]
    l2: float = 1.0
    weights: np.ndarray | None = None
    means: np.ndarray | None = None
    scales: np.ndarray | None = None
    medians: np.ndarray | None = None
    bias: float = 0.0
    history: list[float] = field(default_factory=list)

    # ------------------------------------------------------------------
    def _matrix(self, x: list[list[float]]) -> np.ndarray:
        matrix = np.asarray(x, dtype=np.float64)
        if matrix.ndim == 1:
            matrix = matrix.reshape(-1, 1)
        return matrix

    def _impute(self, matrix: np.ndarray) -> np.ndarray:
        medians = np.nanmedian(matrix, axis=0)
        medians = np.where(np.isnan(medians), 0.0, medians)
        if self.medians is None:
            self.medians = medians
        filled = np.where(np.isnan(matrix), self.medians, matrix)
        return filled

    def fit(self, x: list[list[float]], y: list[int]) -> "LogisticSelector":
        matrix = self._impute(self._matrix(x))
        if self.means is None:
            self.means = matrix.mean(axis=0)
            self.scales = matrix.std(axis=0)
            self.scales = np.where(self.scales < 1e-9, 1.0, self.scales)
        standard = (matrix - self.means) / self.scales
        labels = np.asarray(y, dtype=np.float64)
        n_features = standard.shape[1]
        initial = np.zeros(n_features + 1)

        def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
            w, b = params[:n_features], params[-1]
            logits = standard @ w + b
            logits = np.clip(logits, -30, 30)
            # stable log-loss
            loss = np.mean(np.logaddexp(0.0, logits) - labels * logits)
            loss += 0.5 * self.l2 * float(w @ w) / len(labels)
            prob = 1.0 / (1.0 + np.exp(-logits))
            grad_w = standard.T @ (prob - labels) / len(labels) + self.l2 * w / len(labels)
            grad_b = float(np.mean(prob - labels))
            return loss, np.concatenate([grad_w, [grad_b]])

        from scipy.optimize import minimize

        result = minimize(
            lambda p: objective(p)[0],
            initial,
            jac=lambda p: objective(p)[1],
            method="L-BFGS-B",
            options={"maxiter": 500},
        )
        self.weights = result.x[:n_features]
        self.bias = float(result.x[-1])
        self.history.append(float(result.fun))
        return self

    def predict_proba(self, x: list[list[float]]) -> np.ndarray:
        if self.weights is None:
            raise RuntimeError("Selector is not fitted.")
        matrix = self._impute(self._matrix(x))
        standard = (matrix - self.means) / self.scales
        logits = np.clip(standard @ self.weights + self.bias, -30, 30)
        return 1.0 / (1.0 + np.exp(-logits))

    def to_dict(self) -> dict:
        if self.weights is None:
            return {"feature_names": self.feature_names, "fitted": False}
        return {
            "feature_names": self.feature_names,
            "fitted": True,
            "l2": self.l2,
            "bias": round(self.bias, 4),
            "weights": {
                name: round(float(weight), 4)
                for name, weight in zip(self.feature_names, self.weights)
            },
            "medians": {
                name: None if math.isnan(float(value)) else round(float(value), 4)
                for name, value in zip(self.feature_names, self.medians)
            },
            "means": {
                name: round(float(value), 6)
                for name, value in zip(self.feature_names, self.means)
            },
            "scales": {
                name: round(float(value), 6)
                for name, value in zip(self.feature_names, self.scales)
            },
            "final_loss": round(self.history[-1], 5) if self.history else None,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LogisticSelector":
        """Rehydrate a selector saved with :meth:`to_dict`."""
        if not payload.get("fitted"):
            raise ValueError("selector payload is not fitted")
        names = list(payload["feature_names"])
        return cls(
            feature_names=names,
            l2=float(payload.get("l2", 1.0)),
            weights=np.asarray([payload["weights"][name] for name in names], dtype=float),
            means=np.asarray([payload["means"][name] for name in names], dtype=float),
            scales=np.asarray([payload["scales"][name] for name in names], dtype=float),
            medians=np.asarray(
                [payload["medians"][name] if payload["medians"][name] is not None else np.nan
                 for name in names],
                dtype=float,
            ),
            bias=float(payload.get("bias", 0.0)),
        )
