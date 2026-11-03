"""Evaluate skin-tone and undertone estimation on a consented, labelled dataset.

No accuracy is claimed until this has been run on representative data; see SKIN_ANALYSIS.md.

Manifest CSV columns (labels are optional per row; metrics use the rows that have them):
  path           image file, relative to dataset-root
  person_id      pseudonymous subject ID (one person must stay in one split)
  split          validation | test
  undertone      warm | cool | neutral   (consensus of 2+ trained raters under controlled light)
  monk           1-10                    (rater consensus, Monk Skin Tone scale)
  reference_lab  "L;a;b"                 (colorimeter/spectrophotometer reading of cheek skin, D65)
  groups         optional ";"-separated key=value labels, e.g. "monk_band=7-8;lighting=indoor"

    python scripts/evaluate_skin.py manifest.csv dataset-root                       # validation
    python scripts/evaluate_skin.py manifest.csv dataset-root --sweep-band 1.5,2.5,3.5 --sweep-reference-hue 50,55,60
    python scripts/evaluate_skin.py manifest.csv dataset-root --fit-reference reference.json
    python scripts/evaluate_skin.py manifest.csv dataset-root --evaluate-test       # once, settings frozen

A fitted reference is used by setting SKIN_UNDERTONE_REFERENCE_PATH=reference.json.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, get_settings  # noqa: E402
from app.services.color import delta_e_2000, hue_angle, ita_degrees  # noqa: E402
from app.services.evaluation import check_person_split, rate, resolve_inside  # noqa: E402
from app.services.face_analysis import FaceAnalysisError, FaceAnalyzer, load_oriented_rgb  # noqa: E402
from app.services.skin_analysis import SkinAnalysisUnavailable, analyze_skin, classify_undertone  # noqa: E402

UNDERTONES = ("warm", "neutral", "cool")
MIN_GROUP_SIZE = 30  # people; smaller groups are reported but flagged as not conclusive
MIN_FIT_BIN = 15  # labelled-neutral images per lightness bin when fitting a reference curve


@dataclass
class Row:
    path: Path
    person_id: str
    split: str
    undertone: str | None
    monk: int | None
    reference_lab: np.ndarray | None
    groups: list[str] = field(default_factory=list)


@dataclass
class Outcome:
    status: str  # ok | face error code | skin error code
    skin_lab: np.ndarray | None = None
    monk: int | None = None
    undertone: str | None = None
    undertone_confidence: float | None = None


def read_manifest(manifest: Path, dataset_root: Path) -> list[Row]:
    root = dataset_root.resolve()
    rows = []
    with manifest.open(newline="", encoding="utf-8") as source:
        for line, record in enumerate(csv.DictReader(source), start=2):
            split = record["split"].strip().lower()
            if split not in {"validation", "test"}:
                raise ValueError(f"line {line}: split must be validation or test")
            undertone = (record.get("undertone") or "").strip().lower() or None
            if undertone not in (None, *UNDERTONES):
                raise ValueError(f"line {line}: undertone must be warm, cool or neutral")
            monk = int(record["monk"]) if (record.get("monk") or "").strip() else None
            if monk is not None and not 1 <= monk <= 10:
                raise ValueError(f"line {line}: monk must be 1-10")
            reference = (record.get("reference_lab") or "").strip()
            reference_lab = np.array([float(v) for v in reference.split(";")]) if reference else None
            groups = [g.strip() for g in (record.get("groups") or "").split(";") if g.strip()]
            rows.append(
                Row(resolve_inside(root, record["path"]), record["person_id"].strip(), split, undertone, monk, reference_lab, groups)
            )
    if not rows:
        raise ValueError("Manifest is empty")
    check_person_split(rows)
    return rows


def analyze_rows(rows: list[Row], settings: Settings) -> list[Outcome]:
    outcomes = []
    with FaceAnalyzer(settings) as analyzer:
        for row in rows:
            rgb, corrected = load_oriented_rgb(row.path.read_bytes())
            try:
                skin = analyze_skin(rgb, analyzer.analyze(rgb, orientation_corrected=corrected), settings)
            except (FaceAnalysisError, SkinAnalysisUnavailable) as exc:
                outcomes.append(Outcome(exc.code))
                continue
            lab = skin["skin_tone"]["lab"]
            outcomes.append(
                Outcome(
                    "ok",
                    np.array([lab["l"], lab["a"], lab["b"]]),
                    skin["skin_tone"]["monk"]["value"],
                    skin["undertone"]["value"],
                    skin["undertone"]["confidence"],
                )
            )
    return outcomes


def reclassify(outcomes: list[Outcome], settings: Settings) -> list[Outcome]:
    """Undertone depends only on the skin colour, so threshold sweeps need no re-analysis."""
    result = []
    for o in outcomes:
        if o.skin_lab is None:
            result.append(o)
        else:
            value, confidence, _, _ = classify_undertone(o.skin_lab, settings)
            result.append(Outcome(o.status, o.skin_lab, o.monk, value, confidence))
    return result


def undertone_metrics(pairs: list[tuple[Row, Outcome]]) -> dict:
    labelled = [(row.undertone, o.undertone, o.undertone_confidence or 0.0) for row, o in pairs if row.undertone and o.undertone]
    if not labelled:
        return {"n": 0}
    matrix = {t: dict.fromkeys(UNDERTONES, 0) for t in UNDERTONES}
    for truth, predicted, _ in labelled:
        matrix[truth][predicted] += 1
    per_class = {}
    for c in UNDERTONES:
        tp = matrix[c][c]
        predicted = sum(matrix[t][c] for t in UNDERTONES)
        actual = sum(matrix[c].values())
        precision, recall = rate(tp, predicted), rate(tp, actual)
        f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else 0.0
        per_class[c] = {"precision": precision, "recall": recall, "f1": f1, "support": actual}
    n = len(labelled)
    observed = sum(matrix[c][c] for c in UNDERTONES) / n
    expected = sum(sum(matrix[c].values()) * sum(matrix[t][c] for t in UNDERTONES) for c in UNDERTONES) / n**2
    confident = [(t, p) for t, p, confidence in labelled if confidence >= 0.5]
    return {
        "n": n,
        "accuracy": round(observed, 4),
        "macro_f1": round(float(np.mean([v["f1"] for v in per_class.values()])), 4),
        "cohen_kappa": round((observed - expected) / (1 - expected), 4) if expected < 1 else None,
        "per_class": per_class,
        "confusion_matrix": {"rows_are": "label", "columns_are": "prediction", **matrix},
        "confident_only": {"coverage": rate(len(confident), n), "accuracy": rate(sum(t == p for t, p in confident), len(confident))},
    }


def tone_metrics(pairs: list[tuple[Row, Outcome]]) -> dict:
    with_reference = [(row.reference_lab, o.skin_lab) for row, o in pairs if row.reference_lab is not None and o.skin_lab is not None]
    with_monk = [(row.monk, o.monk) for row, o in pairs if row.monk and o.monk]
    metrics: dict = {"reference_n": len(with_reference), "monk_n": len(with_monk)}
    if with_reference:
        de = np.array([float(delta_e_2000(ref, est)) for ref, est in with_reference])
        ita_error = np.array([abs(float(ita_degrees(ref)) - float(ita_degrees(est))) for ref, est in with_reference])
        metrics |= {
            "delta_e_2000": {
                "mean": round(float(de.mean()), 2),
                "median": round(float(np.median(de)), 2),
                "p90": round(float(np.percentile(de, 90)), 2),
                "within_5": rate(int((de <= 5).sum()), len(de)),
            },
            "ita_abs_error_mean": round(float(ita_error.mean()), 2),
        }
    if with_monk:
        diff = np.array([abs(a - b) for a, b in with_monk])
        metrics["monk"] = {
            "exact": rate(int((diff == 0).sum()), len(diff)),
            "within_1": rate(int((diff <= 1).sum()), len(diff)),
            "mae": round(float(diff.mean()), 3),
        }
    return metrics


def summarize(pairs: list[tuple[Row, Outcome]]) -> dict:
    statuses: dict[str, int] = defaultdict(int)
    for _, o in pairs:
        statuses[o.status] += 1
    return {
        "images": len(pairs),
        "people": len({row.person_id for row, _ in pairs}),
        "analyzed_rate": rate(statuses["ok"], len(pairs)),
        "outcomes": dict(sorted(statuses.items())),
        "skin_tone": tone_metrics(pairs),
        "undertone": undertone_metrics(pairs),
    }


def report(rows: list[Row], outcomes: list[Outcome]) -> dict:
    pairs = list(zip(rows, outcomes, strict=True))
    groups: dict[str, list] = defaultdict(list)
    for row, o in pairs:
        for label in row.groups or ["unlabelled"]:
            groups[label].append((row, o))
        if row.monk:  # Always break results down by depth: undertone methods are easily confounded with it.
            groups[f"monk={row.monk}"].append((row, o))
    by_group = {}
    for label, members in sorted(groups.items()):
        summary = summarize(members)
        summary["conclusive"] = summary["people"] >= MIN_GROUP_SIZE
        by_group[label] = summary
    return {"overall": summarize(pairs), "groups": by_group, "min_group_people": MIN_GROUP_SIZE}


def fit_reference(rows: list[Row], outcomes: list[Outcome]) -> dict:
    """Lightness-dependent neutral hue: median hue of labelled-neutral images per L* quantile bin."""
    points = sorted(
        (float(o.skin_lab[0]), float(hue_angle(o.skin_lab)))
        for row, o in zip(rows, outcomes, strict=True)
        if row.undertone == "neutral" and o.skin_lab is not None
    )
    bins = len(points) // MIN_FIT_BIN
    if bins < 2:
        raise ValueError(f"Need at least {2 * MIN_FIT_BIN} labelled-neutral validation images to fit a reference (have {len(points)})")
    curve = []
    for chunk in np.array_split(np.array(points), bins):
        curve.append([round(float(np.median(chunk[:, 0])), 2), round(float(np.median(chunk[:, 1])), 2)])
    return {"points": curve, "fitted_on": "validation", "neutral_images": len(points)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--evaluate-test", action="store_true", help="Evaluate the held-out test split (once, after freezing settings).")
    parser.add_argument("--sweep-band", help="Comma-separated SKIN_UNDERTONE_NEUTRAL_DELTA_H values (validation only).")
    parser.add_argument("--sweep-reference-hue", help="Comma-separated SKIN_UNDERTONE_REFERENCE_HUE values (validation only).")
    parser.add_argument("--fit-reference", type=Path, help="Fit a lightness-dependent reference on validation and write it here.")
    parser.add_argument("--output", type=Path, help="Also write the JSON report here.")
    args = parser.parse_args()
    tuning = args.sweep_band or args.sweep_reference_hue or args.fit_reference
    if args.evaluate_test and tuning:
        parser.error("Sweeps and fitting are only allowed on the validation split.")

    split = "test" if args.evaluate_test else "validation"
    rows = [row for row in read_manifest(args.manifest, args.dataset_root) if row.split == split]
    if not rows:
        raise SystemExit(f"No rows in the {split} split")
    settings = get_settings()
    outcomes = analyze_rows(rows, settings)

    if args.fit_reference:
        curve = fit_reference(rows, outcomes)
        args.fit_reference.write_text(json.dumps(curve, indent=2), encoding="utf-8")
        print(f"Wrote {args.fit_reference}. Re-run validation with SKIN_UNDERTONE_REFERENCE_PATH set to compare.")
        return
    if args.sweep_band or args.sweep_reference_hue:
        bands = [float(v) for v in (args.sweep_band or str(settings.skin_undertone_neutral_delta_h)).split(",")]
        hues = [float(v) for v in (args.sweep_reference_hue or str(settings.skin_undertone_reference_hue)).split(",")]
        result = {"split": split, "sweep": []}
        for band, hue in itertools.product(bands, hues):
            swept = settings.model_copy(update={"skin_undertone_neutral_delta_h": band, "skin_undertone_reference_hue": hue})
            metrics = report(rows, reclassify(outcomes, swept))
            result["sweep"].append(
                {
                    "neutral_delta_h": band,
                    "reference_hue": hue,
                    "overall": metrics["overall"]["undertone"],
                    "per_monk": {k: v["undertone"] for k, v in metrics["groups"].items() if k.startswith("monk=")},
                }
            )
    else:
        result = {"split": split, **report(rows, outcomes)}
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
