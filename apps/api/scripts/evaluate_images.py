"""Evaluate image suitability rules from a labeled CSV without claiming unmeasured accuracy.

Manifest columns: path,label,split,group. Labels are suitable/unsuitable; split is
validation/test. Paths must remain under dataset-root. Evaluate test only after thresholds
are frozen from validation data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from app.config import Settings, get_settings
from app.services.image_validation import ImageValidationError, validate_image


def evaluate(
    manifest: Path,
    dataset_root: Path,
    split: str,
    *,
    min_blur_variance: float | None = None,
    min_brightness: float | None = None,
) -> dict:
    entries: list[tuple[bool, bool, str]] = []
    updates = {}
    if min_blur_variance is not None:
        updates["selfie_min_blur_variance"] = min_blur_variance
    if min_brightness is not None:
        updates["selfie_min_brightness"] = min_brightness
    settings: Settings = get_settings().model_copy(update=updates)
    root = dataset_root.resolve()
    with manifest.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row["split"].strip().lower() != split:
                continue
            path = (root / row["path"]).resolve()
            if root not in path.parents:
                raise ValueError("Manifest path escapes the dataset root")
            label = row["label"].strip().lower()
            if label not in {"suitable", "unsuitable"}:
                raise ValueError("Labels must be suitable or unsuitable")
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower())
            if mime is None:
                raise ValueError(f"Unsupported dataset image extension: {path.suffix}")
            try:
                prediction = validate_image(path.read_bytes(), path.name, mime, settings).valid
            except ImageValidationError:
                prediction = False
            entries.append((label == "suitable", prediction, row.get("group", "unspecified")))

    if not entries:
        raise ValueError(f"No rows in {split!r} split")
    tp = sum(actual and predicted for actual, predicted, _ in entries)
    tn = sum(not actual and not predicted for actual, predicted, _ in entries)
    fp = sum(not actual and predicted for actual, predicted, _ in entries)
    fn = sum(actual and not predicted for actual, predicted, _ in entries)
    groups: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for actual, predicted, group in entries:
        groups[group].append((actual, predicted))
    return {
        "split": split,
        "samples": len(entries),
        "confusion_matrix": {"labels": ["unsuitable", "suitable"], "matrix": [[tn, fp], [fn, tp]]},
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_acceptance_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_rejection_rate": fn / (fn + tp) if fn + tp else 0.0,
        "groups": {
            group: {
                "samples": len(rows),
                "false_accepts": sum(not actual and predicted for actual, predicted in rows),
                "false_rejects": sum(actual and not predicted for actual, predicted in rows),
            }
            for group, rows in sorted(groups.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--evaluate-test", action="store_true")
    parser.add_argument("--blur-sweep", help="Comma-separated minimum Laplacian variances; validation split only")
    parser.add_argument("--brightness-sweep", help="Comma-separated minimum grayscale means; validation split only")
    args = parser.parse_args()
    report = evaluate(args.manifest, args.dataset_root, "validation")
    if args.blur_sweep:
        report["blur_threshold_sensitivity"] = {
            value: evaluate(args.manifest, args.dataset_root, "validation", min_blur_variance=float(value))
            for value in args.blur_sweep.split(",")
        }
    if args.brightness_sweep:
        report["brightness_threshold_sensitivity"] = {
            value: evaluate(args.manifest, args.dataset_root, "validation", min_brightness=float(value))
            for value in args.brightness_sweep.split(",")
        }
    print(json.dumps(report, indent=2))
    if args.evaluate_test:
        print(json.dumps(evaluate(args.manifest, args.dataset_root, "test"), indent=2))


if __name__ == "__main__":
    main()
