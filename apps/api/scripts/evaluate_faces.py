"""Evaluate face detection, landmarks and regions on a consented, annotated dataset.

No accuracy is claimed until this has been run on representative data; see FACE_ANALYSIS.md.

Manifest CSV columns:
  path            image file, relative to dataset-root
  person_id       pseudonymous subject ID (splits are checked per person to prevent identity leakage)
  split           validation | test
  expected_faces  0, 1, or 2+ (any number >= 2)
  groups          optional, ";"-separated key=value labels, e.g. "skin_tone=V;eyewear=glasses;pose=tilted"
  annotation      optional JSON file (relative to dataset-root) with ground truth in pixels of the
                  EXIF-oriented image:
                    {"landmarks": {"33": [x, y], "263": [x, y], ...},     # any MediaPipe indices
                     "regions": {"left_cheek": [[x, y], ...], ...}}        # polygons

    python scripts/evaluate_faces.py manifest.csv dataset-root                     # validation split
    python scripts/evaluate_faces.py manifest.csv dataset-root --sweep-confidence 0.3,0.5,0.7
    python scripts/evaluate_faces.py manifest.csv dataset-root --evaluate-test     # once, thresholds frozen
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, get_settings  # noqa: E402
from app.services.evaluation import check_person_split, rate, resolve_inside  # noqa: E402
from app.services.face_analysis import FaceAnalysisError, FaceAnalyzer  # noqa: E402

NME_THRESHOLDS = (0.05, 0.10)
MIN_GROUP_SIZE = 30  # Below this, a group's numbers are reported but flagged as not conclusive.


@dataclass
class Row:
    path: Path
    person_id: str
    split: str
    expected_faces: int
    groups: list[str]
    annotation: dict = field(default_factory=dict)


def read_manifest(manifest: Path, dataset_root: Path) -> list[Row]:
    root = dataset_root.resolve()
    rows = []
    with manifest.open(newline="", encoding="utf-8") as source:
        for line, record in enumerate(csv.DictReader(source), start=2):
            split = record["split"].strip().lower()
            if split not in {"validation", "test"}:
                raise ValueError(f"line {line}: split must be validation or test")
            expected = record["expected_faces"].strip()
            faces = 2 if expected.endswith("+") else int(expected)
            labels = [g.strip() for g in (record.get("groups") or "").split(";") if g.strip()]
            annotation = {}
            if (record.get("annotation") or "").strip():
                annotation = json.loads(resolve_inside(root, record["annotation"].strip()).read_text(encoding="utf-8"))
            rows.append(Row(resolve_inside(root, record["path"]), record["person_id"].strip(), split, min(faces, 2), labels, annotation))
    if not rows:
        raise ValueError("Manifest is empty")
    check_person_split(rows)
    return rows


def _mask(polygon: list[list[float]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.round(np.asarray(polygon)).astype(np.int32)], 1)
    return mask.astype(bool)


def evaluate_row(analyzer: FaceAnalyzer, row: Row) -> dict:
    """Outcome for one image: what was predicted, and landmark/region errors when annotated."""
    try:
        analysis = analyzer.analyze_bytes(row.path.read_bytes())
    except FaceAnalysisError as exc:
        predicted = 2 if exc.code == "MULTIPLE_FACES_DETECTED" else (1 if exc.code == "FACE_LANDMARKS_NOT_FOUND" else 0)
        return {"predicted_faces": predicted, "code": exc.code}
    result: dict = {"predicted_faces": 1, "code": "OK", "warnings": [w["code"] for w in analysis.warnings]}

    truth = row.annotation.get("landmarks", {})
    if truth:
        indices = [int(i) for i in truth]
        expected = np.array([truth[str(i)] for i in indices], dtype=float)
        got = np.array([[analysis.landmarks[i]["px"], analysis.landmarks[i]["py"]] for i in indices])
        span = expected.max(axis=0) - expected.min(axis=0)
        face_size = math.sqrt(max(span[0], 1) * max(span[1], 1))  # bounding-box normalization
        errors = np.linalg.norm(got - expected, axis=1) / face_size
        result["nme"] = float(errors.mean())
        result["landmark_errors"] = errors.tolist()

    regions = row.annotation.get("regions", {})
    if regions:
        shape = (analysis.image_height, analysis.image_width)
        ious = {}
        for name, polygon in regions.items():
            predicted = analysis.regions.get(name, {}).get("polygon") or analysis.regions.get(name, {}).get("polyline")
            if not predicted:
                continue
            a, b = _mask(polygon, shape), _mask(predicted, shape)
            union = np.logical_or(a, b).sum()
            ious[name] = float(np.logical_and(a, b).sum() / union) if union else 0.0
        result["region_iou"] = ious
    return result


def summarize(pairs: list[tuple[Row, dict]]) -> dict:
    face_present = [(row.expected_faces >= 1, out["predicted_faces"] >= 1) for row, out in pairs]
    tp = sum(a and p for a, p in face_present)
    fp = sum(not a and p for a, p in face_present)
    fn = sum(a and not p for a, p in face_present)
    tn = sum(not a and not p for a, p in face_present)
    precision, recall = rate(tp, tp + fp), rate(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else None

    single = [out for row, out in pairs if row.expected_faces == 1]
    multi = [out for row, out in pairs if row.expected_faces == 2]
    none = [out for row, out in pairs if row.expected_faces == 0]
    errors = [e for _, out in pairs for e in out.get("landmark_errors", [])]
    nmes = [out["nme"] for _, out in pairs if "nme" in out]
    ious: dict[str, list[float]] = defaultdict(list)
    for _, out in pairs:
        for name, value in out.get("region_iou", {}).items():
            ious[name].append(value)

    return {
        "images": len(pairs),
        "people": len({row.person_id for row, _ in pairs}),
        "detection": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1},
        "single_face_acceptance_rate": rate(sum(o["code"] == "OK" for o in single), len(single)),
        "multiple_face_rejection_rate": rate(sum(o["code"] == "MULTIPLE_FACES_DETECTED" for o in multi), len(multi)),
        "no_face_rejection_rate": rate(sum(o["code"] == "NO_FACE_DETECTED" for o in none), len(none)),
        "landmarks": {
            "annotated_images": len(nmes),
            "mean_nme": round(float(np.mean(nmes)), 4) if nmes else None,
            "median_nme": round(float(np.median(nmes)), 4) if nmes else None,
            **{f"within_{t:g}": rate(sum(e <= t for e in errors), len(errors)) for t in NME_THRESHOLDS},
        },
        "regions": {
            name: {"n": len(v), "mean_iou": round(float(np.mean(v)), 4), "iou_at_least_0.5": rate(sum(x >= 0.5 for x in v), len(v))}
            for name, v in sorted(ious.items())
        },
        "outcomes": dict(sorted(_count(out["code"] for _, out in pairs).items())),
    }


def _count(items) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item] += 1
    return counts


def evaluate(rows: list[Row], split: str, settings: Settings) -> dict:
    selected = [row for row in rows if row.split == split]
    if not selected:
        raise ValueError(f"No rows in the {split!r} split")
    with FaceAnalyzer(settings) as analyzer:
        pairs = [(row, evaluate_row(analyzer, row)) for row in selected]
    by_group: dict[str, list[tuple[Row, dict]]] = defaultdict(list)
    for row, out in pairs:
        for label in row.groups or ["unlabelled"]:
            by_group[label].append((row, out))
    groups = {}
    for label, members in sorted(by_group.items()):
        summary = summarize(members)
        summary["conclusive"] = summary["people"] >= MIN_GROUP_SIZE
        groups[label] = summary
    return {"split": split, "overall": summarize(pairs), "groups": groups, "min_group_people": MIN_GROUP_SIZE}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--evaluate-test", action="store_true", help="Evaluate the held-out test split (once, after freezing thresholds).")
    parser.add_argument("--sweep-confidence", help="Comma-separated FACE_MIN_DETECTION_CONFIDENCE values (validation only).")
    parser.add_argument("--output", type=Path, help="Also write the JSON report here.")
    args = parser.parse_args()
    if args.evaluate_test and args.sweep_confidence:
        parser.error("Threshold sweeps are only allowed on the validation split.")

    rows = read_manifest(args.manifest, args.dataset_root)
    base = get_settings()
    split = "test" if args.evaluate_test else "validation"
    if args.sweep_confidence:
        report = {
            "split": split,
            "sweep": {
                value: evaluate(rows, split, base.model_copy(update={"face_min_detection_confidence": float(value)}))["overall"]
                for value in (v.strip() for v in args.sweep_confidence.split(","))
            },
        }
    else:
        report = evaluate(rows, split, base)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
