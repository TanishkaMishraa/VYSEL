"""Eye colour, hair colour and feature contrast (Phase 4.4).

All colours use the same white-balanced scene as skin analysis (`skin_analysis.prepare_scene`).

* **Eye colour**: iris pixels inside MediaPipe's iris circle (centre + 4 documented ring points),
  clipped by the eyelid contour (eyelids cover part of the iris), without the pupil; lashes,
  shadow and catch-lights are trimmed by lightness percentiles. Both eyes are combined when they
  agree.
* **Hair colour**: a band around the top of the head, oriented along the face's own up-axis so a
  tilted head works. Skin-coloured pixels are removed (forehead, scalp), KMeans splits the rest,
  and the hair cluster must be clearly different from a background reference sampled further from
  the face. When hair cannot be told apart from skin or background, the result is "unavailable"
  rather than a guess.
* **Feature contrast**: lightness difference between hair (or eyes) and skin, the input the
  recommendation engine calls `contrast`.

Category boundaries are untuned starting values (see FACIAL_ATTRIBUTES.md); every value is an
estimate with a heuristic confidence until evaluated with scripts/evaluate_attributes.py.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from app.config import Settings, get_settings
from app.services.color import chroma, delta_e_2000, hue_angle, lab_to_hex
from app.services.face_analysis import FaceAnalysis
from app.services.face_region_data import FEATURE_LANDMARKS, REGION_LANDMARKS
from app.services.skin_analysis import Scene, _polygon_mask

EYE_COLORS = ("dark_brown", "brown", "hazel", "green", "blue", "gray")
HAIR_COLORS = ("black", "dark_brown", "brown", "light_brown", "blonde", "red", "gray", "white", "other")

_PUPIL_RATIO = 0.35  # pupil radius / iris radius, mid-range for indoor and daylight photos
_IRIS_DISK_RATIO = 0.9  # stay inside the limbal ring
_EYES_AGREE_DELTA_E = 15.0
_HAIR_KMEANS = 3


class AttributeUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message

    def as_json(self) -> dict[str, Any]:
        return {"status": "unavailable", "error": {"code": self.code, "message": self.message}}


def _lab_json(lab: np.ndarray) -> dict[str, float]:
    return {"l": round(float(lab[0]), 2), "a": round(float(lab[1]), 2), "b": round(float(lab[2]), 2)}


def _pixels(face: FaceAnalysis) -> np.ndarray:
    return np.array([(p["px"], p["py"]) for p in face.landmarks])


def _lighting_factor(scene: Scene, settings: Settings) -> float:
    if scene.correction["clamped"]:
        return 0.5
    size = min(1.0, float(np.max(np.abs(np.log(scene.gains)))) / math.log(settings.skin_wb_max_gain))
    return 1.0 - 0.4 * size


# ── Eye colour ─────────────────────────────────────────────────────────────


def classify_eye(lab: np.ndarray) -> str:
    c, h, lightness = float(chroma(lab)), float(hue_angle(lab)), float(lab[0])
    if c < 4:
        return "gray" if lightness >= 40 else "dark_brown"
    if 180 <= h < 330:  # blue side (-b*)
        return "blue" if c >= 6 else "gray"
    if 90 <= h < 180:  # green side (-a*, +b*)
        return "green"
    if lightness < 35:
        return "dark_brown"
    return "brown" if lightness < 50 else "hazel"


def _iris_sample(face: FaceAnalysis, scene: Scene, side: str, settings: Settings) -> tuple[np.ndarray | None, str, int]:
    """(median Lab or None, reason, pixel count) for one eye."""
    points = _pixels(face)
    centre = points[FEATURE_LANDMARKS[f"{side}_iris_center"][0]]
    radius = float(np.mean(np.linalg.norm(points[list(FEATURE_LANDMARKS[f"{side}_iris"])] - centre, axis=1)))
    if radius < settings.eye_min_iris_radius_px:
        return None, "iris_too_small", 0
    shape = scene.clipped.shape
    disk = np.zeros(shape, np.uint8)
    cv2.circle(disk, (round(centre[0]), round(centre[1])), round(radius * _IRIS_DISK_RATIO), 1, -1)
    pupil = np.zeros(shape, np.uint8)
    cv2.circle(pupil, (round(centre[0]), round(centre[1])), max(1, round(radius * _PUPIL_RATIO)), 1, -1)
    eyelids = _polygon_mask(points[list(FEATURE_LANDMARKS[f"{side}_eye"])].tolist(), shape)
    mask = disk.astype(bool) & eyelids.astype(bool) & ~pupil.astype(bool)
    visible = mask.sum() / max(1, (disk.astype(bool) & ~pupil.astype(bool)).sum())
    if visible < 0.3:
        return None, "eye_closed_or_covered", int(mask.sum())
    lab = scene.lab(mask)
    if len(lab) < settings.eye_min_pixels:
        return None, "too_few_pixels", int(len(lab))
    low, high = np.percentile(lab[:, 0], [15, 85])  # lashes and shadow below, catch-lights above
    lab = lab[(lab[:, 0] >= low) & (lab[:, 0] <= high)]
    return np.median(lab, axis=0), "ok", int(len(lab))


def analyze_eye_color(face: FaceAnalysis, scene: Scene, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    samples = {side: _iris_sample(face, scene, side, cfg) for side in ("left", "right")}
    usable = {side: (lab, n) for side, (lab, _, n) in samples.items() if lab is not None}
    eyes = {side: {"used": lab is not None, "reason": reason, "pixels": n} for side, (lab, reason, n) in samples.items()}
    if not usable:
        raise AttributeUnavailable(
            "EYES_NOT_VISIBLE", "The irises are too small, closed or covered to read eye colour. Move closer, eyes open."
        )

    warnings = []
    if len(usable) == 2:
        (left, n_left), (right, n_right) = usable["left"], usable["right"]
        if float(delta_e_2000(left, right)) <= _EYES_AGREE_DELTA_E:
            lab = (left * n_left + right * n_right) / (n_left + n_right)
        else:
            side = "left" if n_left >= n_right else "right"
            lab = usable[side][0]
            eyes["right" if side == "left" else "left"]["used"] = False
            eyes["right" if side == "left" else "left"]["reason"] = "differs_from_other_eye"
            warnings.append({"code": "EYES_DIFFER", "message": "The two eyes look different (lighting, reflection or heterochromia)."})
    else:
        lab = next(iter(usable.values()))[0]
    for side, (sample, _) in usable.items():
        if eyes[side]["used"]:
            eyes[side]["lab"] = _lab_json(sample)

    pixels = sum(n for side, (_, n) in usable.items() if eyes[side]["used"])
    confidence = min(1.0, pixels / 150) * (1.0 if len(usable) == 2 and not warnings else 0.75) * _lighting_factor(scene, cfg)
    value = classify_eye(lab)
    return {
        "status": "ok",
        "value": value,
        "confidence": round(0.85 * confidence, 3),  # small pixel areas: never near-certain
        "label": "estimate",
        "hex": lab_to_hex(lab),
        "lab": _lab_json(lab),
        "eyes": eyes,
        "warnings": warnings,
    }


# ── Hair colour ────────────────────────────────────────────────────────────


def classify_hair(lab: np.ndarray) -> str:
    c, h, lightness = float(chroma(lab)), float(hue_angle(lab)), float(lab[0])
    if c >= 12 and not 10 <= h <= 100:  # blue, green, purple, pink: dyed
        return "other"
    if c < 6:  # no measurable hue: black, gray (incl. salt-and-pepper) or white, by lightness
        return "black" if lightness < 35 else "gray" if lightness < 75 else "white"
    if lightness < 20:
        return "black"
    if c >= 25 and h < 60:  # saturated orange-red: ginger, copper, auburn
        return "red"
    if lightness >= 55 and lab[2] >= 12:
        return "blonde"
    if lightness < 32:
        return "dark_brown"
    return "brown" if lightness < 48 else "light_brown"


def _scaled(polygon: np.ndarray, centre: np.ndarray, factor: float, offset: np.ndarray | None = None) -> list[list[float]]:
    moved = centre + (polygon - centre) * factor
    return (moved + (offset if offset is not None else 0)).tolist()


def analyze_hair_color(face: FaceAnalysis, scene: Scene, skin_lab: np.ndarray | None, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    points = _pixels(face)
    shape = scene.clipped.shape
    oval = np.asarray(face.regions["face_oval"]["polyline"])
    centre = oval.mean(axis=0)
    top, chin = points[REGION_LANDMARKS["forehead_top"][0]], points[REGION_LANDMARKS["chin_bottom"][0]]
    up = (top - chin) / np.linalg.norm(top - chin)  # the face's own up direction (handles roll)
    face_length = float(np.linalg.norm(top - chin))
    temples = (points[REGION_LANDMARKS["left_forehead_edge"][0]] + points[REGION_LANDMARKS["right_forehead_edge"][0]]) / 2

    # Face-aligned coordinates: u = distance above the mesh top along the face's up axis,
    # v = sideways offset from the face's centre line. The mesh stops mid-forehead, so first find
    # the hairline by walking up a central strip until most pixels stop looking like skin.
    ys, xs = np.mgrid[0 : shape[0], 0 : shape[1]]
    right = np.array([-up[1], up[0]])
    u = (xs - top[0]) * up[0] + (ys - top[1]) * up[1]
    v = (xs - temples[0]) * right[0] + (ys - temples[1]) * right[1]
    face_width = scene.face_width
    above = ((xs - temples[0]) * up[0] + (ys - temples[1]) * up[1]) > 0

    hairline = 0.1 * face_length  # without a skin colour, assume hair starts just above the mesh
    if skin_lab is not None:
        strip = (np.abs(v) < 0.3 * face_width) & (u > 0) & (u < 0.6 * face_length)
        strip_lab, strip_u = scene.lab(strip), u[strip & ~scene.clipped]
        if len(strip_lab) < cfg.hair_min_pixels:
            raise AttributeUnavailable("HAIR_NOT_VISIBLE", "The top of the head is not in the photo, so hair colour can't be read.")
        not_skin = delta_e_2000(strip_lab, skin_lab) >= cfg.hair_skin_delta_e
        step = 0.02 * face_length
        found = None
        for start_u in np.arange(0, 0.5 * face_length, step):
            rows = (strip_u >= start_u) & (strip_u < start_u + step)
            if rows.sum() >= 20 and not_skin[rows].mean() >= 0.5:
                found = float(start_u)
                break
        if found is None:
            raise AttributeUnavailable(
                "HAIR_NOT_VISIBLE",
                "Little hair is visible above the forehead (very short hair, a shaved head, a covering, or hair close to skin colour).",
            )
        hairline = found

    band = (np.abs(v) < 0.35 * face_width) & (u >= hairline) & (u < hairline + 0.15 * face_length)
    lab = scene.lab(band)
    if len(lab) < cfg.hair_min_pixels:
        raise AttributeUnavailable("HAIR_NOT_VISIBLE", "Not enough of the area above the forehead is in the photo to read hair colour.")

    cv2.setRNGSeed(cfg.skin_kmeans_seed)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.05)
    # Background reference: pixels well away from the head and level with or above the temples, so
    # clothing below the face does not count as background.
    background = scene.lab(~_polygon_mask(_scaled(oval, centre, 2.2), shape).astype(bool) & above, limit=20000)
    background_centres = None
    if len(background) >= 100:
        _, _, background_centres = cv2.kmeans(background.astype(np.float32), 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

    # Cluster the band above the hairline (skin included: scalp showing through, ears).
    sample = lab[np.linspace(0, len(lab) - 1, min(len(lab), 20000)).astype(int)]
    k = max(1, min(_HAIR_KMEANS, len(sample) // 50))
    _, labels, centres = cv2.kmeans(sample.astype(np.float32), k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    shares = np.bincount(labels, minlength=k) / len(labels)
    clusters = []
    for i in range(k):
        skin_distance = float(delta_e_2000(centres[i], skin_lab)) if skin_lab is not None else math.inf
        background_distance = float(np.min(delta_e_2000(background_centres, centres[i]))) if background_centres is not None else math.inf
        clusters.append({"index": i, "share": float(shares[i]), "skin_delta_e": skin_distance, "background_delta_e": background_distance})
    not_skin = [c for c in clusters if c["skin_delta_e"] >= cfg.hair_skin_delta_e and c["share"] >= 0.15]
    if not not_skin:
        raise AttributeUnavailable(
            "HAIR_NOT_VISIBLE",
            "Little hair is visible around the face (very short hair, a shaved head, a covering, or hair close to skin colour).",
        )
    # The hair is the dominant non-skin colour next to the face. If that colour also fills the
    # background, report it as unmeasurable rather than falling back to a minor cluster.
    chosen = max(not_skin, key=lambda c: c["share"])
    if chosen["background_delta_e"] < cfg.hair_background_delta_e:
        raise AttributeUnavailable("HAIR_NOT_SEPARABLE", "Hair colour is too close to the background to measure. Try a plainer background.")
    hair_lab = np.median(sample[labels == chosen["index"]], axis=0)

    separation = min(1.0, chosen["background_delta_e"] / 20) if math.isfinite(chosen["background_delta_e"]) else 0.6
    confidence = (0.5 + 0.5 * chosen["share"]) * separation * _lighting_factor(scene, cfg)
    warnings = []
    if background_centres is None:
        warnings.append({"code": "HAIR_BACKGROUND_UNKNOWN", "message": "Too little background is visible to separate hair from it."})
    return {
        "status": "ok",
        "value": classify_hair(hair_lab),
        "confidence": round(0.85 * confidence, 3),  # hats and backgrounds can still fool it
        "label": "estimate",
        "hex": lab_to_hex(hair_lab),
        "lab": _lab_json(hair_lab),
        "band_pixels": int(len(lab)),
        "background_delta_e": round(chosen["background_delta_e"], 1) if math.isfinite(chosen["background_delta_e"]) else None,
        "warnings": warnings,
    }


# ── Contrast ───────────────────────────────────────────────────────────────


def feature_contrast(skin: dict[str, Any] | None, hair: dict[str, Any], eyes: dict[str, Any], settings: Settings) -> dict[str, Any] | None:
    """Lightness contrast between hair (else eyes) and skin: low | medium | high."""
    if not skin or skin.get("status") != "ok":
        return None
    source = hair if hair.get("status") == "ok" else eyes if eyes.get("status") == "ok" else None
    if source is None:
        return None
    difference = abs(source["lab"]["l"] - skin["skin_tone"]["lab"]["l"])
    low, high = settings.contrast_low_max_delta_l, settings.contrast_medium_max_delta_l
    value = "low" if difference < low else "medium" if difference < high else "high"
    margin = min(abs(difference - low), abs(difference - high)) / 10
    confidence = min(source["confidence"], skin["skin_tone"]["confidence"]) * (0.6 + 0.4 * min(1.0, margin))
    return {
        "value": value,
        "confidence": round(confidence, 3),
        "label": "estimate",
        "delta_l": round(difference, 1),
        "source": "hair" if source is hair else "eyes",
    }
