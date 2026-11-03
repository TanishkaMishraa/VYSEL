"""Shared helpers for the offline evaluation scripts (scripts/evaluate_*.py)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol


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
