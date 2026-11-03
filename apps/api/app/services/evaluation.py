"""Shared helpers for the offline evaluation scripts (scripts/evaluate_*.py)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol


class _Split(Protocol):
    person_id: str
    split: str


def resolve_inside(root: Path, relative: str) -> Path:
    """Resolve a manifest path, refusing anything outside the dataset root."""
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"Manifest path escapes the dataset root: {relative}")
    return path


def check_person_split(rows: Iterable[_Split]) -> None:
    """Every person must be in exactly one split, or test results leak identity information."""
    splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        splits[row.person_id].add(row.split)
    leaked = sorted(person for person, names in splits.items() if len(names) > 1)
    if leaked:
        raise ValueError(f"{len(leaked)} person_id(s) appear in both splits (identity leakage): {', '.join(leaked[:5])}")


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def classification_metrics(pairs: list[tuple[str, str, float]], classes: Sequence[str]) -> dict[str, Any]:
    """Metrics for (label, prediction, confidence) triples over a fixed class list.

    Includes the majority-class baseline: a classifier is only useful if it beats always
    answering the most common label.
    """
    if not pairs:
        return {"n": 0}
    n = len(pairs)
    matrix = {t: dict.fromkeys(classes, 0) for t in classes}
    for truth, predicted, _ in pairs:
        matrix[truth][predicted] += 1
    per_class = {}
    for c in classes:
        tp = matrix[c][c]
        precision, recall = rate(tp, sum(matrix[t][c] for t in classes)), rate(tp, sum(matrix[c].values()))
        f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else 0.0
        per_class[c] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[c].values())}
    observed = sum(matrix[c][c] for c in classes) / n
    expected = sum(sum(matrix[c].values()) * sum(matrix[t][c] for t in classes) for c in classes) / n**2
    supported = [v["f1"] for v in per_class.values() if v["support"]]
    confident = [(t, p) for t, p, confidence in pairs if confidence >= 0.5]
    majority = max(per_class.values(), key=lambda v: v["support"])["support"]
    return {
        "n": n,
        "accuracy": round(observed, 4),
        "majority_baseline_accuracy": round(majority / n, 4),
        "macro_f1": round(sum(supported) / len(supported), 4) if supported else None,
        "cohen_kappa": round((observed - expected) / (1 - expected), 4) if expected < 1 else None,
        "per_class": per_class,
        "confusion_matrix": {"rows_are": "label", "columns_are": "prediction", **matrix},
        "confident_only": {"coverage": rate(len(confident), n), "accuracy": rate(sum(t == p for t, p in confident), len(confident))},
    }
