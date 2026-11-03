"""Evaluate face shape, eye colour and hair colour on a consented, labelled dataset.

No accuracy is claimed until this has been run on representative data; see FACIAL_ATTRIBUTES.md.

Manifest CSV columns (labels optional per row; metrics use the rows that have them):
  path               image file, relative to dataset-root
  person_id          pseudonymous subject ID (one person must stay in one split)
  split              validation | test
  face_shape         oval | round | square | heart | oblong | diamond   (rater 1)
  face_shape_rater2  same vocabulary, an independent second rater (measures how far raters agree)
  eye_color          dark_brown | brown | hazel | green | blue | gray
  hair_color         black | dark_brown | brown | light_brown | blonde | red | gray | white | other
  groups             optional ";"-separated key=value labels, e.g. "monk=7;eyewear=glasses"

    python scripts/evaluate_attributes.py manifest.csv dataset-root                     # validation
    python scripts/evaluate_attributes.py manifest.csv dataset-root --fit-prototypes models/face_shape.json
    python scripts/evaluate_attributes.py manifest.csv dataset-root --evaluate-test     # once, settings frozen

A fitted face-shape model is used by setting FACE_SHAPE_PROTOTYPES_PATH.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, get_settings  # noqa: E402
from app.services.appearance import analyze_appearance  # noqa: E402
from app.services.evaluation import check_person_split, classification_metrics, rate, resolve_inside  # noqa: E402
from app.services.face_analysis import FaceAnalysisError, FaceAnalyzer, load_oriented_rgb  # noqa: E402
from app.services.face_shape import FEATURES, SHAPES  # noqa: E402
from app.services.facial_attributes import EYE_COLORS, HAIR_COLORS  # noqa: E402

ATTRIBUTES = {"face_shape": SHAPES, "eye_color": EYE_COLORS, "hair_color": HAIR_COLORS}
MIN_GROUP_SIZE = 30  # people
MIN_FIT_PER_CLASS = 10  # labelled validation faces per shape to fit its prototype


@dataclass
class Row:
    path: Path
    person_id: str
    split: str
    labels: dict[str, str]
    rater2: str | None
    groups: list[str] = field(default_factory=list)


def read_manifest(manifest: Path, dataset_root: Path) -> list[Row]:
    root = dataset_root.resolve()
    rows = []
    with manifest.open(newline="", encoding="utf-8") as source:
        for line, record in enumerate(csv.DictReader(source), start=2):
            split = record["split"].strip().lower()
            if split not in {"validation", "test"}:
                raise ValueError(f"line {line}: split must be validation or test")
            labels = {}
            for attribute, vocabulary in ATTRIBUTES.items():
                value = (record.get(attribute) or "").strip().lower()
                if value and value not in vocabulary:
                    raise ValueError(f"line {line}: {attribute} must be one of {', '.join(vocabulary)}")
                if value:
                    labels[attribute] = value
            rater2 = (record.get("face_shape_rater2") or "").strip().lower() or None
            if rater2 and rater2 not in SHAPES:
                raise ValueError(f"line {line}: face_shape_rater2 must be one of {', '.join(SHAPES)}")
            groups = [g.strip() for g in (record.get("groups") or "").split(";") if g.strip()]
            rows.append(Row(resolve_inside(root, record["path"]), record["person_id"].strip(), split, labels, rater2, groups))
    if not rows:
        raise ValueError("Manifest is empty")
    check_person_split(rows)
    return rows


def analyze_rows(rows: list[Row], settings: Settings) -> list[dict]:
    """Per image: predicted value/confidence per attribute (None if unavailable) and face-shape features."""
    outcomes = []
    with FaceAnalyzer(settings) as analyzer:
        for row in rows:
            started = perf_counter()
            rgb, corrected = load_oriented_rgb(row.path.read_bytes())
            try:
                attributes = analyze_appearance(rgb, analyzer.analyze(rgb, orientation_corrected=corrected), settings)["attributes"]
            except FaceAnalysisError as exc:
                outcomes.append({"status": exc.code, "processing_time_ms": (perf_counter() - started) * 1000})
                continue
            outcome: dict = {"status": "ok"}
            for name in ATTRIBUTES:
                result = attributes[name]
                outcome[name] = (result["value"], result["confidence"]) if result["status"] == "ok" else None
            shape = attributes["face_shape"]
            outcome["features"] = shape.get("features")
            outcome["processing_time_ms"] = (perf_counter() - started) * 1000
            outcomes.append(outcome)
    return outcomes


def summarize(pairs: list[tuple[Row, dict]]) -> dict:
    summary: dict = {"images": len(pairs), "people": len({row.person_id for row, _ in pairs})}
    summary["face_analyzed_rate"] = rate(sum(o["status"] == "ok" for _, o in pairs), len(pairs))
    timings = sorted(float(o["processing_time_ms"]) for _, o in pairs if o.get("processing_time_ms") is not None)
    if timings:
        summary["processing_time_ms"] = {
            "n": len(timings),
            "mean": round(mean(timings), 2),
            "median": round(float(np.percentile(timings, 50)), 2),
            "p95": round(float(np.percentile(timings, 95)), 2),
            "images_per_second": round(1000 / mean(timings), 2) if mean(timings) else None,
        }
    for name, vocabulary in ATTRIBUTES.items():
        labelled = [(row, o) for row, o in pairs if name in row.labels]
        predicted = [(row.labels[name], o[name][0], o[name][1]) for row, o in labelled if o.get(name)]
        metrics = classification_metrics(predicted, vocabulary)
        metrics["available_rate"] = rate(len(predicted), len(labelled))
        summary[name] = metrics
    both = [(row.labels["face_shape"], row.rater2, 1.0) for row, _ in pairs if row.rater2 and "face_shape" in row.labels]
    if both:
        agreement = classification_metrics(both, SHAPES)
        # The model cannot be held to more than the raters' own agreement on face shape.
        summary["face_shape_rater_agreement"] = {k: agreement[k] for k in ("n", "accuracy", "cohen_kappa")}
    return summary


def report(rows: list[Row], outcomes: list[dict]) -> dict:
    pairs = list(zip(rows, outcomes, strict=True))
    groups: dict[str, list] = defaultdict(list)
    for row, outcome in pairs:
        for label in row.groups or ["unlabelled"]:
            groups[label].append((row, outcome))
    by_group = {}
    for label, members in sorted(groups.items()):
        summary = summarize(members)
        summary["conclusive"] = summary["people"] >= MIN_GROUP_SIZE
        by_group[label] = summary
    return {"overall": summarize(pairs), "groups": by_group, "min_group_people": MIN_GROUP_SIZE}


def fit_prototypes(rows: list[Row], outcomes: list[dict]) -> dict:
    """Nearest-prototype model from labelled validation faces: class means, pooled within-class spread."""
    by_shape: dict[str, list[list[float]]] = defaultdict(list)
    for row, outcome in zip(rows, outcomes, strict=True):
        if "face_shape" in row.labels and outcome.get("features"):
            by_shape[row.labels["face_shape"]].append([outcome["features"][f] for f in FEATURES])
    usable = {shape: np.array(values) for shape, values in by_shape.items() if len(values) >= MIN_FIT_PER_CLASS}
    if len(usable) < 2:
        raise ValueError(f"Need at least {MIN_FIT_PER_CLASS} labelled validation faces for two or more shapes")
    residuals = np.concatenate([values - values.mean(axis=0) for values in usable.values()])
    spread = np.maximum(residuals.std(axis=0, ddof=len(usable)), 1e-6)
    return {
        "prototypes": {shape: (values.mean(axis=0) / spread).round(4).tolist() for shape, values in sorted(usable.items())},
        "spread": dict(zip(FEATURES, spread.round(6).tolist(), strict=True)),
        "fitted_on": "validation",
        "faces_per_shape": {shape: len(values) for shape, values in sorted(usable.items())},
        "skipped_shapes": sorted(set(by_shape) - set(usable)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--evaluate-test", action="store_true", help="Evaluate the held-out test split (once, after freezing settings).")
    parser.add_argument("--fit-prototypes", type=Path, help="Fit face-shape prototypes on validation and write them here.")
    parser.add_argument("--output", type=Path, help="Also write the JSON report here.")
    args = parser.parse_args()
    if args.evaluate_test and args.fit_prototypes:
        parser.error("Fitting is only allowed on the validation split.")

    split = "test" if args.evaluate_test else "validation"
    rows = [row for row in read_manifest(args.manifest, args.dataset_root) if row.split == split]
    if not rows:
        raise SystemExit(f"No rows in the {split} split")
    outcomes = analyze_rows(rows, get_settings())
    if args.fit_prototypes:
        model = fit_prototypes(rows, outcomes)
        args.fit_prototypes.write_text(json.dumps(model, indent=2), encoding="utf-8")
        print(f"Wrote {args.fit_prototypes}. Re-run validation with FACE_SHAPE_PROTOTYPES_PATH set to compare.")
        return
    text = json.dumps({"split": split, **report(rows, outcomes)}, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
