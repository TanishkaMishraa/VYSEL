"""Skin colour and undertone estimation from a face scan (Phase 4.3).

Pipeline (all colour maths in linear light and CIELAB D65, see `color.py`):

1. White balance: estimate the illuminant with Shades of Gray (Finlayson & Trezzi, 2004) on
   pixels *outside* the face, so the person's own skin cannot pull the correction, and apply
   bounded von Kries gains. Exposure is deliberately not normalized: it would shift skin depth.
2. Skin pixels: fill the visible Phase 4.2 area regions (forehead, cheeks, chin), erode away
   from their edges, drop clipped pixels, then drop per-region colour outliers (hair, glasses,
   highlights, shadows) with a robust median/MAD rule in CIEDE2000.
3. Region consistency: a region whose colour differs strongly from the others is excluded
   (a hand, mask, heavy shadow or makeup over that region).
4. KMeans (OpenCV, seeded) on the pooled pixels separates shading bands; the skin colour is the
   share-weighted mean of the clusters, leaving out minor clusters far from the typical pixel.
5. Skin tone: ITA (Chardon et al., 1991), its category, the contract's depth bucket, and the
   nearest Monk Skin Tone swatch.
6. Undertone: CIELAB hue angle of the skin colour relative to a reference hue, measured as the
   perceptual hue difference dH (CIEDE units). Inside the neutral band -> neutral.

Every output is an estimate with a heuristic, uncalibrated confidence until evaluated
(scripts/evaluate_skin.py, SKIN_ANALYSIS.md).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.config import Settings, get_settings
from app.services.color import (
    chroma,
    delta_e_2000,
    hex_to_lab,
    hue_angle,
    ita_degrees,
    lab_to_hex,
    linear_to_lab,
    srgb8_to_linear,
)
from app.services.face_analysis import FaceAnalysis
from app.services.face_regions import AREA_REGIONS

UNDERTONE_METHOD = "cielab-hue-v1"

# Monk Skin Tone scale (Google, 2022), the published reference swatches.
MONK_SCALE = ("#F6EDE4", "#F3E7DB", "#F7EAD0", "#EADABA", "#D7BD96", "#A07E56", "#825C43", "#604134", "#3A312A", "#292420")
_MONK_LAB = np.array([hex_to_lab(h) for h in MONK_SCALE])

# ITA categories (Chardon et al., 1991; Del Bino & Bernerd, 2013) and the contract's SkinDepth.
ITA_CATEGORIES = (
    (55, "very_light", "fair"),
    (41, "light", "light"),
    (28, "intermediate", "medium"),
    (10, "tan", "tan"),
    (-30, "brown", "deep"),
    (-math.inf, "dark", "deep"),
)

_CLIP_HIGH, _CLIP_LOW = 250, 5  # uint8 sRGB
_MAX_WB_PIXELS = 100_000  # An evenly spaced sample estimates the illuminant just as well.
_MAX_PIXELS_PER_REGION = 6000  # Equal weight per region; also bounds CPU time.
_MAD_SCALE = 1.4826  # MAD -> standard deviation for normally distributed data.
_OUTLIER_SIGMAS = 3.0
_MINOR_CLUSTER_SHARE = 0.15


class SkinAnalysisUnavailable(Exception):
    def __init__(self, code: str, message: str, warnings: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.code, self.message, self.warnings = code, message, warnings or []

    def as_json(self) -> dict[str, Any]:
        return {"status": "unavailable", "error": {"code": self.code, "message": self.message}, "warnings": self.warnings}


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _lab_json(lab: np.ndarray) -> dict[str, float]:
    return {"l": round(float(lab[0]), 2), "a": round(float(lab[1]), 2), "b": round(float(lab[2]), 2)}


# ── 1. White balance ───────────────────────────────────────────────────────


def estimate_white_balance(linear: np.ndarray, reference: np.ndarray, settings: Settings) -> tuple[np.ndarray, dict[str, Any]]:
    """Per-channel gains from Shades of Gray over `reference` pixels (a boolean mask)."""
    pixels = linear[reference]
    info: dict[str, Any] = {"method": settings.skin_white_balance, "reference_pixels": int(len(pixels))}
    pixels = _sample(pixels, _MAX_WB_PIXELS)
    if settings.skin_white_balance == "none" or len(pixels) < 100:
        info |= {"gains": {"r": 1.0, "g": 1.0, "b": 1.0}, "clamped": False, "applied": False}
        return np.ones(3), info
    p = settings.skin_wb_minkowski_p
    illuminant = np.mean(pixels**p, axis=0) ** (1 / p)
    gains = illuminant.mean() / np.maximum(illuminant, 1e-6)
    limit = settings.skin_wb_max_gain
    clamped = bool(np.any(gains > limit) or np.any(gains < 1 / limit))
    gains = np.clip(gains, 1 / limit, limit)
    info |= {"gains": dict(zip("rgb", (round(float(g), 4) for g in gains), strict=True)), "clamped": clamped, "applied": True}
    return gains, info


# ── 2-3. Skin pixels ───────────────────────────────────────────────────────


def _polygon_mask(points: list[list[float]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.round(np.asarray(points)).astype(np.int32)], 1)
    return mask


def _robust_inliers(lab: np.ndarray) -> np.ndarray:
    """Pixels within 3 robust standard deviations (CIEDE2000) of the region's median colour."""
    distance = delta_e_2000(lab, np.median(lab, axis=0))
    centre = np.median(distance)
    spread = _MAD_SCALE * np.median(np.abs(distance - centre))
    return distance <= centre + _OUTLIER_SIGMAS * max(spread, 0.5)


def _sample(pixels: np.ndarray, limit: int) -> np.ndarray:
    if len(pixels) <= limit:
        return pixels
    return pixels[np.linspace(0, len(pixels) - 1, limit).astype(int)]  # deterministic, spatially even


# ── 5-6. Classification ────────────────────────────────────────────────────


def ita_category(ita: float) -> tuple[str, str]:
    for threshold, category, depth in ITA_CATEGORIES:
        if ita > threshold:
            return category, depth
    raise AssertionError("unreachable")


def nearest_monk(lab: np.ndarray) -> tuple[int, float]:
    distances = delta_e_2000(_MONK_LAB, lab)
    index = int(np.argmin(distances))
    return index + 1, float(distances[index])


@lru_cache
def _reference_curve(path: str | None) -> tuple[np.ndarray, np.ndarray] | None:
    if not path:
        return None
    points = sorted(json.loads(Path(path).read_text(encoding="utf-8"))["points"])
    return np.array([p[0] for p in points], dtype=float), np.array([p[1] for p in points], dtype=float)


def reference_hue(lightness: float, settings: Settings) -> float:
    """Neutral reference hue: a constant, or a lightness-dependent curve fitted on validation data."""
    curve = _reference_curve(str(settings.skin_undertone_reference_path) if settings.skin_undertone_reference_path else None)
    if curve is None:
        return settings.skin_undertone_reference_hue
    return float(np.interp(lightness, curve[0], curve[1]))


def hue_difference(lab: np.ndarray, reference: float) -> float:
    """Signed perceptual hue difference dH (CIEDE units) between `lab` and the reference hue at the same chroma.

    Positive = more yellow (warmer), negative = more red/pink (cooler). Scales with chroma, so
    low-chroma skin, whose undertone is hardest to judge, sits closer to neutral.
    """
    delta = (float(hue_angle(lab)) - reference + 180) % 360 - 180
    return 2 * float(chroma(lab)) * math.sin(math.radians(delta / 2))


def classify_undertone(lab: np.ndarray, settings: Settings) -> tuple[str, float, float, float]:
    """(value, base confidence, signed dH, reference hue)."""
    reference = reference_hue(float(lab[0]), settings)
    dh = hue_difference(lab, reference)
    s = dh / settings.skin_undertone_neutral_delta_h
    value = "warm" if s > 1 else "cool" if s < -1 else "neutral"
    margin = abs(abs(s) - 1)  # distance to the nearest class boundary, in band widths
    return value, 0.5 + 0.45 * min(1.0, margin), dh, reference


# ── Main entry point ───────────────────────────────────────────────────────


@dataclass
class _Region:
    name: str
    lab: np.ndarray  # inlier pixels
    median: np.ndarray


@dataclass
class Scene:
    """An image prepared for colour measurement: linear light plus the white-balance correction."""

    linear: np.ndarray  # (H, W, 3) linear sRGB, uncorrected
    clipped: np.ndarray  # (H, W) pixels too bright or too dark to measure
    gains: np.ndarray  # per-channel von Kries gains
    correction: dict[str, Any]
    face_mask: np.ndarray  # face oval enlarged 30% (hair, ears and neck included)
    face_width: float
    warnings: list[dict[str, str]]

    def lab(self, mask: np.ndarray, limit: int | None = None) -> np.ndarray:
        """White-balanced CIELAB of the unclipped pixels in `mask`; at most `limit`, evenly spaced."""
        index = np.flatnonzero(mask & ~self.clipped)
        if limit is not None and len(index) > limit:
            index = index[np.linspace(0, len(index) - 1, limit).astype(int)]
        return linear_to_lab(np.clip(self.linear.reshape(-1, 3)[index] * self.gains, 0, 1))


def prepare_scene(rgb: np.ndarray, face: FaceAnalysis, settings: Settings | None = None) -> Scene:
    """Estimate the white balance from everything outside the (enlarged) face. Shared by skin,
    eye and hair colour so all of them use the same correction."""
    cfg = settings or get_settings()
    height, width = rgb.shape[:2]
    if (width, height) != (face.image_width, face.image_height):
        raise ValueError("The image does not match the face scan's dimensions")
    clipped = np.any(rgb >= _CLIP_HIGH, axis=2) | np.all(rgb <= _CLIP_LOW, axis=2)
    linear = srgb8_to_linear(rgb)
    oval = np.asarray(face.regions["face_oval"]["polyline"])
    centre = oval.mean(axis=0)
    face_mask = _polygon_mask((centre + (oval - centre) * 1.3).tolist(), (height, width)).astype(bool)
    gains, correction = estimate_white_balance(linear, ~face_mask & ~clipped, cfg)
    warnings = []
    if correction["applied"] and correction["reference_pixels"] < 0.05 * width * height:
        warnings.append(_warning("WHITE_BALANCE_LIMITED", "Little background is visible, so colour correction is less reliable."))
    if correction["clamped"]:
        warnings.append(_warning("STRONG_COLOR_CAST", "The lighting has a strong colour tint; colour estimates are less reliable."))
    face_width = float(oval[:, 0].max() - oval[:, 0].min())
    return Scene(linear, clipped, gains, correction, face_mask, face_width, warnings)


def analyze_skin(rgb: np.ndarray, face: FaceAnalysis, settings: Settings | None = None, scene: Scene | None = None) -> dict[str, Any]:
    """Estimate skin tone and undertone. `rgb` is the EXIF-oriented uint8 image the face scan used.

    Raises SkinAnalysisUnavailable when no usable skin is visible.
    """
    cfg = settings or get_settings()
    scene = scene or prepare_scene(rgb, face, cfg)
    height, width = rgb.shape[:2]
    gains, correction, face_width = scene.gains, scene.correction, scene.face_width
    warnings: list[dict[str, str]] = list(scene.warnings)

    # 2. Skin pixels per visible region.
    erosion = max(1, round(face_width * cfg.skin_mask_erosion_ratio))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * erosion + 1, 2 * erosion + 1))
    regions: dict[str, _Region] = {}
    report: dict[str, dict[str, Any]] = {}
    for name in AREA_REGIONS:
        geometry = face.regions[name]
        if not geometry.get("visible"):
            report[name] = {"used": False, "reason": "not_visible", "pixels": 0}
            continue
        lab = scene.lab(cv2.erode(_polygon_mask(geometry["polygon"], (height, width)), kernel).astype(bool))
        if len(lab) < cfg.skin_min_pixels_per_region:
            report[name] = {"used": False, "reason": "too_few_pixels", "pixels": int(len(lab))}
            continue
        lab = _sample(lab[_robust_inliers(lab)], _MAX_PIXELS_PER_REGION)
        regions[name] = _Region(name, lab, np.median(lab, axis=0))

    if not regions:
        raise SkinAnalysisUnavailable(
            "NO_VISIBLE_SKIN", "Not enough clear skin is visible. Face the camera in even light, without anything covering your face."
        )

    # 3. Exclude regions that disagree with the rest (needs 3+ regions to tell which one is off).
    consensus = np.median(np.array([r.median for r in regions.values()]), axis=0)
    spread = {name: float(delta_e_2000(r.median, consensus)) for name, r in regions.items()}
    if len(regions) >= 3:
        for name in [n for n, d in spread.items() if d > cfg.skin_region_max_delta_e]:
            report[name] = {"used": False, "reason": "color_inconsistent", "pixels": int(len(regions[name].lab))}
            label = name.replace("_", " ")
            message = f"The {label} looks different from the rest of the face (shadow, makeup or a covering) and was left out."
            warnings.append(_warning("REGION_COLOR_INCONSISTENT", message))
            del regions[name]
    elif max(spread.values()) > cfg.skin_region_max_delta_e:
        warnings.append(
            _warning(
                "REGION_COLOR_INCONSISTENT", "Visible skin areas differ strongly in colour (uneven light or something covering the face)."
            )
        )
    for name, region in regions.items():
        report[name] = {
            "used": True,
            "pixels": int(len(region.lab)),
            "lab": _lab_json(region.median),
            "hex": lab_to_hex(region.median),
            "delta_e_from_consensus": round(spread[name], 2),
        }

    pooled = np.concatenate([r.lab for r in regions.values()])
    if len(pooled) < cfg.skin_min_pixels:
        raise SkinAnalysisUnavailable("INSUFFICIENT_SKIN_PIXELS", "Too little clear skin is visible. Move closer to the camera.", warnings)

    # 4. KMeans: the largest cluster is the skin colour; smaller ones absorb shading and highlights.
    k = max(1, min(cfg.skin_kmeans_clusters, len(pooled) // 50))
    cv2.setRNGSeed(cfg.skin_kmeans_seed)
    _, labels, centres = cv2.kmeans(
        pooled.astype(np.float32),
        k,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.05),
        5,
        cv2.KMEANS_PP_CENTERS,
    )
    shares = np.bincount(labels.ravel(), minlength=k) / len(labels)
    order = np.argsort(-shares)
    centres = centres.astype(np.float64)
    # Skin colour = share-weighted mean of the clusters, without minor clusters far from the
    # typical pixel (residual shadow, stubble, highlights). Taking only the largest cluster is
    # unstable: clusters split skin into shading bands, and which band is largest flips with k
    # or with one region being hidden (measured: up to 6 L* / 5.8 dE on the same face).
    median = np.median(pooled, axis=0)
    outlying = (shares < _MINOR_CLUSTER_SHARE) & (delta_e_2000(centres, median) > cfg.skin_region_max_delta_e / 2)
    used = ~outlying if (~outlying).any() else np.ones(k, bool)
    skin_lab = (centres[used] * shares[used, None]).sum(axis=0) / shares[used].sum()
    used_share = float(shares[used].sum())
    clusters = [
        {"lab": _lab_json(centres[i]), "hex": lab_to_hex(centres[i]), "share": round(float(shares[i]), 4), "used": bool(used[i])}
        for i in order
    ]

    # 5. Skin tone.
    ita = float(ita_degrees(skin_lab))
    category, depth = ita_category(ita)
    monk, monk_distance = nearest_monk(skin_lab)

    # 6. Undertone, and how consistently the regions agree on it.
    undertone, undertone_confidence, dh, ref = classify_undertone(skin_lab, cfg)
    region_dh = [hue_difference(r.median, reference_hue(float(r.median[0]), cfg)) for r in regions.values()]
    if len(region_dh) >= 2 and max(region_dh) - min(region_dh) > 2 * cfg.skin_undertone_neutral_delta_h:
        undertone_confidence *= 0.7
        warnings.append(
            _warning(
                "UNDERTONE_REGIONS_DISAGREE", "Different parts of the face suggest different undertones; treat the undertone as uncertain."
            )
        )

    # Heuristic confidences (not calibrated; see SKIN_ANALYSIS.md). Undertone is penalized more
    # for colour correction than skin tone: residual white-balance error moves hue about as much
    # as the neutral band is wide (measured on simulated casts), while lightness barely moves.
    correction_size = min(1.0, float(np.max(np.abs(np.log(gains)))) / math.log(cfg.skin_wb_max_gain))
    coverage = min(1.0, len(pooled) / (4 * cfg.skin_min_pixels))
    agreement = 1.0 - 0.5 * min(1.0, max(spread[n] for n in regions) / cfg.skin_region_max_delta_e)
    tone_confidence = (0.6 if correction["clamped"] else 1.0 - 0.3 * correction_size) * coverage * agreement * (0.6 + 0.4 * used_share)
    undertone_confidence *= (1.0 - 0.6 * correction_size) * coverage
    if correction["clamped"]:
        undertone_confidence = min(undertone_confidence, 0.3)
    if undertone_confidence < 0.5:
        warnings.append(
            _warning("LOW_CONFIDENCE_UNDERTONE", "Undertone is uncertain for this photo; daylight facing a window gives the best result.")
        )

    return {
        "status": "ok",
        "skin_tone": {
            "hex": lab_to_hex(skin_lab),
            "lab": _lab_json(skin_lab),
            "depth": depth,
            "confidence": round(tone_confidence, 3),
            "label": "estimate",
            "ita_degrees": round(ita, 1),
            "ita_category": category,
            "monk": {"value": monk, "hex": MONK_SCALE[monk - 1], "delta_e": round(monk_distance, 2)},
        },
        "undertone": {
            "value": undertone,
            "confidence": round(undertone_confidence, 3),
            "label": "estimate",
            "method": UNDERTONE_METHOD,
            "hue_angle": round(float(hue_angle(skin_lab)), 1),
            "chroma": round(float(chroma(skin_lab)), 1),
            "reference_hue": round(ref, 1),
            "delta_h": round(dh, 2),
        },
        "color_correction": correction,
        "clusters": clusters,
        "regions": report,
        "pixels_used": int(len(pooled)),
        "warnings": warnings,
    }
