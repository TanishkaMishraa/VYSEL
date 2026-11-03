"""Single-face detection and landmark extraction with MediaPipe (Phase 4.2).

Pipeline for one image that already passed Phase 4.1 validation:

1. Decode and apply EXIF orientation, so coordinates match the image as people see it.
2. Count faces with MediaPipe's BlazeFace detector (which also gives a confidence score) and
   cross-check with the Face Landmarker. Exactly one face is required.
3. Extract MediaPipe's 478 face landmarks (normalized x, y, z plus pixel coordinates).
4. Map landmarks to regions (`face_regions`), estimate head pose and report warnings for
   conditions that make downstream skin/shape analysis less reliable.

Both models come from one pinned, hash-verified bundle (`face_landmarker.task`); its embedded
`face_detector.tflite` is the BlazeFace short-range detector.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.config import Settings, get_settings
from app.services.face_regions import AREA_REGIONS, CONTOUR_REGIONS, KEY_POINTS, REGIONS, in_frame_ratio, region_geometry

log = logging.getLogger(__name__)

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
MODEL_NAME = "mediapipe-face-landmarker/float16/1"
LANDMARK_COUNT = 478  # 468 face-mesh points + 10 iris points (documented MediaPipe topology).


class FaceAnalysisError(Exception):
    """A user-facing rejection (no face, several faces, ...). Safe to return to clients."""

    def __init__(self, code: str, message: str, *, face_count: int = 0, warnings: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.code, self.message, self.face_count = code, message, face_count
        self.warnings = warnings or []


class FaceModelUnavailable(RuntimeError):
    """MediaPipe or the model file is missing or invalid. Logged with setup instructions; clients see a 503."""


@dataclass
class FaceAnalysis:
    face_count: int
    image_width: int
    image_height: int
    orientation_corrected: bool
    rotation_applied: int
    detection: dict[str, Any]
    landmarks: list[dict[str, float | int]]
    regions: dict[str, dict]
    key_points: dict[str, dict]
    head_pose: dict[str, float]
    warnings: list[dict[str, str]] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "face_count": self.face_count,
            "image": {
                "width": self.image_width,
                "height": self.image_height,
                "orientation_corrected": self.orientation_corrected,
                "rotation_applied_degrees": self.rotation_applied,
            },
            "detection": self.detection,
            "landmarks": {
                "count": len(self.landmarks),
                "topology": "mediapipe-face-mesh-478",
                "coordinate_space": (
                    "x, y normalized to [0, 1] by image width/height (may fall slightly outside when the face "
                    "leaves the frame); z is relative depth on the same scale as x, smaller is closer; "
                    "px, py are pixels in the EXIF-oriented image."
                ),
                "points": self.landmarks,
            },
            "regions": self.regions,
            "key_points": self.key_points,
            "head_pose": self.head_pose,
            "warnings": self.warnings,
        }


def load_oriented_rgb(data: bytes) -> tuple[np.ndarray, bool]:
    """Decode to an RGB array in display orientation. Returns (pixels, orientation_was_corrected)."""
    with Image.open(BytesIO(data)) as image:
        image.load()
        try:
            orientation = image.getexif().get(0x0112, 1)  # EXIF Orientation tag; 1 = already upright.
            oriented = ImageOps.exif_transpose(image) if orientation != 1 else image
        except Exception:  # Malformed EXIF must not block analysis; fall back to raw pixels.
            log.info("Ignoring unreadable EXIF orientation")
            orientation, oriented = 1, image
        return np.asarray(oriented.convert("RGB")), orientation != 1


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _unrotate(points: np.ndarray, k: int) -> np.ndarray:
    """Map normalized (x, y) from an image rotated with np.rot90(k) back to the original frame."""
    x, y = points[:, 0], points[:, 1]
    if k == 1:
        x, y = 1 - y, x
    elif k == 2:
        x, y = 1 - x, 1 - y
    elif k == 3:
        x, y = y, 1 - x
    return np.stack([x, y], axis=1)


def _euler_degrees(matrix: np.ndarray) -> tuple[float, float, float]:
    """(pitch, yaw, roll) of the face relative to MediaPipe's canonical frontal pose."""
    rotation = matrix[:3, :3] / np.linalg.norm(matrix[:3, :3], axis=0)
    pitch = math.degrees(math.atan2(rotation[2, 1], rotation[2, 2]))
    yaw = math.degrees(math.asin(float(np.clip(-rotation[2, 0], -1, 1))))
    roll = math.degrees(math.atan2(rotation[1, 0], rotation[0, 0]))
    return pitch, yaw, roll


# Geometric constants, not data-tuned:
# - two boxes are the same face when their intersection covers half of the smaller one (merges
#   landmarker duplicates and a face cut by a search window's edge with its full view);
# - a landmark face must overlap the detector's box at least _MATCH_IOU to belong to it;
# - a roll beyond 45 degrees is closer to a quarter turn than to upright;
# - images at least 1.5x longer than wide get square-window search (see `analyze`).
_SAME_FACE_OVERLAP = 0.5
_MATCH_IOU = 0.1
_SIDEWAYS_ROLL_DEGREES = 45
_WINDOW_ASPECT = 1.5


def _iou(a: np.ndarray, b: np.ndarray | None) -> float:
    """Intersection over union of two (x0, y0, x1, y1) boxes."""
    if b is None:
        return 0.0
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
    return float(w * h / union) if union > 0 else 0.0


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection over the smaller box's area."""
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return float(w * h / smaller) if smaller > 0 else 0.0


def _distinct(boxes: list[np.ndarray]) -> list[np.ndarray]:
    kept: list[np.ndarray] = []
    for box in boxes:
        if all(_overlap(box, other) < _SAME_FACE_OVERLAP for other in kept):
            kept.append(box)
    return kept


@dataclass
class _Pass:
    """Result of running both models on one rotation or window of the image (normalized coordinates)."""

    k: int
    rotated_shape: tuple[int, int]
    boxes: list[np.ndarray]  # one box per distinct face (detector and landmarker combined)
    confidence: float
    box: np.ndarray | None
    face: np.ndarray | None
    pose: tuple[float, float, float]

    @property
    def face_count(self) -> int:
        return len(self.boxes)

    def unreliable(self, low_confidence: float) -> bool:
        return self.face_count == 0 or self.confidence < low_confidence or abs(self.pose[2]) > _SIDEWAYS_ROLL_DEGREES


def _verify_bundle(path: Path) -> bytes:
    try:
        bundle = path.read_bytes()
    except FileNotFoundError:
        raise FaceModelUnavailable(f"Face model not found at {path}. Run: python scripts/setup_face_analysis.py") from None
    if hashlib.sha256(bundle).hexdigest() != MODEL_SHA256:
        raise FaceModelUnavailable(
            f"Face model at {path} does not match the pinned SHA-256. Delete it and run: python scripts/setup_face_analysis.py"
        )
    return bundle


class FaceAnalyzer:
    """Owns the MediaPipe detector and landmarker. Thread-safe; call `close()` (or use `with`)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = cfg = settings or get_settings()
        try:
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:
            raise FaceModelUnavailable("MediaPipe is not installed. Run: python scripts/setup_face_analysis.py") from exc

        bundle = _verify_bundle(cfg.face_model_path)
        with zipfile.ZipFile(BytesIO(bundle)) as archive:
            detector_model = archive.read("face_detector.tflite")
        mode = vision.RunningMode.IMAGE
        self._detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_buffer=detector_model),
                running_mode=mode,
                min_detection_confidence=cfg.face_min_detection_confidence,
            )
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=bundle),
                running_mode=mode,
                num_faces=cfg.face_max_faces_counted,
                min_face_detection_confidence=cfg.face_min_detection_confidence,
                min_face_presence_confidence=cfg.face_min_presence_confidence,
                output_facial_transformation_matrixes=True,
            )
        )
        self._lock = threading.Lock()  # MediaPipe task graphs must not run concurrently.
        self._closed = False
        log.info("Face analyzer ready (%s)", MODEL_NAME)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._detector.close()
                self._landmarker.close()
                self._closed = True

    def __enter__(self) -> FaceAnalyzer:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _infer(self, rgb: np.ndarray) -> tuple[list[Any], Any]:
        import mediapipe as mp

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            if self._closed:
                raise FaceModelUnavailable("Face analyzer has been closed.")
            return self._detector.detect(image).detections, self._landmarker.detect(image)

    def analyze_bytes(self, data: bytes) -> FaceAnalysis:
        rgb, corrected = load_oriented_rgb(data)
        return self.analyze(rgb, orientation_corrected=corrected)

    def analyze(self, rgb: np.ndarray, *, orientation_corrected: bool = False) -> FaceAnalysis:
        """Analyze an RGB uint8 array (H, W, 3) in display orientation."""
        if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
            raise ValueError("Expected an RGB uint8 image of shape (H, W, 3)")
        cfg = self.settings
        height, width = rgb.shape[:2]
        work = rgb
        if max(height, width) > cfg.face_max_inference_side:  # Models crop to 128-256 px anyway.
            scale = cfg.face_max_inference_side / max(height, width)
            work = cv2.resize(rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

        # Analyze the image as oriented. If that looks unreliable (no face, a weak detection, or a
        # face lying sideways or upside down), also try quarter turns and keep the most confident
        # pass: the models are most accurate on upright faces, and an upside-down face can yield a
        # weak false positive elsewhere in the frame instead of no detection at all.
        best = self._pass(work, 0)
        if cfg.face_rotation_search and best.unreliable(cfg.face_low_confidence_warning):
            for k in (1, 3, 2):
                candidate = self._pass(work, k)
                # A rotated pass wins only with a complete, matched face (detector and landmarks
                # agree) and a higher detection confidence; detector-only hits are not trusted.
                if candidate.face is not None and (best.face is None or candidate.confidence > best.confidence):
                    best = candidate
        if best.face_count == 0 and max(work.shape[:2]) >= _WINDOW_ASPECT * min(work.shape[:2]):
            best = self._window_search(work) or best

        if best.face_count == 0:
            raise FaceAnalysisError("NO_FACE_DETECTED", "No face was found. Face the camera in good light and retake the photo.")
        if best.face_count > 1:
            raise FaceAnalysisError(
                "MULTIPLE_FACES_DETECTED",
                "More than one face was found. Take a photo with only your face in the frame.",
                face_count=best.face_count,
            )
        if best.face is None:
            raise FaceAnalysisError(
                "FACE_LANDMARKS_NOT_FOUND",
                "A face was found but its features could not be located. Face the camera directly and retake the photo.",
                face_count=1,
            )

        k = best.k
        rotated_h, rotated_w = best.rotated_shape
        raw = best.face
        normalized = _unrotate(raw[:, :2], k)
        # z shares x's scale in the rotated frame; rescale it to the original image width.
        z = raw[:, 2] * rotated_w / (rotated_h if k in (1, 3) else rotated_w)
        pixels = normalized * np.array([width, height])

        detection = {"confidence": None, "bounding_box": None}
        if best.box is not None:
            mapped = _unrotate(best.box.reshape(2, 2), k) * np.array([width, height])
            x0, y0 = mapped.min(axis=0)
            x1, y1 = mapped.max(axis=0)
            detection = {
                "confidence": round(best.confidence, 4),
                "bounding_box": {
                    "x": round(float(x0), 1),
                    "y": round(float(y0), 1),
                    "width": round(float(x1 - x0), 1),
                    "height": round(float(y1 - y0), 1),
                },
            }
        pitch, yaw, roll = best.pose
        roll = (roll - 90 * k + 180) % 360 - 180  # Express roll in the original (un-rotated) frame.
        head_pose = {"pitch": round(pitch, 1), "yaw": round(yaw, 1), "roll": round(roll, 1)}

        regions = {name: region_geometry(REGIONS[name], pixels, width, height) for name in AREA_REGIONS + CONTOUR_REGIONS}
        key_points = {}
        for name in KEY_POINTS:
            index = REGIONS[name].landmark_indices[0]
            key_points[name] = {
                "index": index,
                "x": round(float(normalized[index, 0]), 5),
                "y": round(float(normalized[index, 1]), 5),
                "px": round(float(pixels[index, 0]), 1),
                "py": round(float(pixels[index, 1]), 1),
            }

        warnings = self._warnings(detection, pixels, width, height, head_pose, k, regions)
        points = [
            {
                "index": i,
                "x": round(float(normalized[i, 0]), 5),
                "y": round(float(normalized[i, 1]), 5),
                "z": round(float(z[i]), 5),
                "px": round(float(pixels[i, 0]), 1),
                "py": round(float(pixels[i, 1]), 1),
            }
            for i in range(len(normalized))
        ]
        return FaceAnalysis(
            face_count=1,
            image_width=width,
            image_height=height,
            orientation_corrected=orientation_corrected,
            rotation_applied=90 * k,
            detection=detection,
            landmarks=points,
            regions=regions,
            key_points=key_points,
            head_pose=head_pose,
            warnings=warnings,
        )

    def _pass(self, work: np.ndarray, k: int = 0, window: tuple[int, int, int] | None = None) -> _Pass:
        """Run both models on `work` rotated by np.rot90(k), or on a square `window` (x0, y0, side).

        Window coordinates are converted to the full image, so a window pass behaves like k=0.
        """
        if window is not None:
            x0, y0, side = window
            view = work[y0 : y0 + side, x0 : x0 + side]
        else:
            view = np.rot90(work, k) if k else work
        height, width = view.shape[:2]
        detections, result = self._infer(view)

        def to_frame(xy: np.ndarray) -> np.ndarray:
            if window is None:
                return xy
            return (xy * side + [x0, y0]) / [work.shape[1], work.shape[0]]

        scored = [
            (
                float(d.categories[0].score),
                np.concatenate(
                    to_frame(
                        np.array(
                            [
                                [d.bounding_box.origin_x / width, d.bounding_box.origin_y / height],
                                [
                                    (d.bounding_box.origin_x + d.bounding_box.width) / width,
                                    (d.bounding_box.origin_y + d.bounding_box.height) / height,
                                ],
                            ]
                        )
                    )
                ),
            )
            for d in detections
        ]
        faces: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for landmarks, matrix in zip(result.face_landmarks, result.facial_transformation_matrixes, strict=False):
            points = np.array([(p.x, p.y, p.z) for p in landmarks], dtype=np.float64)
            points[:, :2] = to_frame(points[:, :2])
            if window is not None:
                points[:, 2] *= side / work.shape[1]  # z shares x's scale; re-express in full-image width
            box = np.concatenate([points[:, :2].min(axis=0), points[:, :2].max(axis=0)])
            # The landmarker can return overlapping copies of one face; keep one.
            if all(_overlap(box, other) < _SAME_FACE_OVERLAP for _, other, _ in faces):
                faces.append((points, box, np.asarray(matrix)))

        boxes = _distinct([box for _, box in scored] + [box for _, box, _ in faces])
        confidence, best_box = max(scored, key=lambda b: b[0]) if scored else (0.0, None)
        face = pose = None
        if faces:
            # Use the landmark set that matches the detector's face; none matching means the two
            # models disagree, and the landmarks cannot be trusted.
            points, face_box, matrix = max(faces, key=lambda f: _iou(f[1], best_box)) if best_box is not None else faces[0]
            if best_box is None or _iou(face_box, best_box) >= _MATCH_IOU:
                face, pose = points, _euler_degrees(matrix)
        shape = (height, width) if window is None else work.shape[:2]
        return _Pass(k, shape, boxes, confidence, best_box, face, pose or (0.0, 0.0, 0.0))

    def _window_search(self, work: np.ndarray) -> _Pass | None:
        """Search an elongated image in overlapping square windows (side = shorter edge).

        Detectors letterbox the whole frame to a small square input, so a face in a panorama-like
        frame can shrink below what the detector sees. Faces are merged across windows.
        """
        height, width = work.shape[:2]
        side, long = min(height, width), max(height, width)
        steps = max(1, math.ceil((long - side) / (side / 2)))
        offsets = sorted({round(i * (long - side) / steps) for i in range(steps + 1)})
        passes = [self._pass(work, window=(o, 0, side) if width > height else (0, o, side)) for o in offsets]
        # As with rotations, only windows where detector and landmarks agree are trusted.
        complete = [p for p in passes if p.face is not None]
        if not complete:
            return None
        best = max(complete, key=lambda p: p.confidence)
        best.boxes = _distinct([box for p in complete for box in p.boxes])
        return best

    def _warnings(
        self, detection: dict, pixels: np.ndarray, width: int, height: int, pose: dict[str, float], k: int, regions: dict[str, dict]
    ) -> list[dict[str, str]]:
        cfg = self.settings
        warnings: list[dict[str, str]] = []
        confidence = detection["confidence"]
        if confidence is None or confidence < cfg.face_low_confidence_warning:
            warnings.append(_warning("LOW_DETECTION_CONFIDENCE", "The face was hard to detect; results may be less accurate."))

        oval = pixels[list(REGIONS["face_oval"].landmark_indices)]
        face_width = float(oval[:, 0].max() - oval[:, 0].min())
        if face_width < cfg.face_min_face_width_px:
            warnings.append(_warning("FACE_LOW_RESOLUTION", "The face is small in the photo. Move closer for more accurate results."))
        if in_frame_ratio(oval, width, height) < cfg.face_min_in_frame_ratio:
            warnings.append(_warning("FACE_PARTIALLY_OUT_OF_FRAME", "Part of the face is outside the photo. Center your face and retake."))

        if (
            abs(pose["yaw"]) > cfg.face_max_yaw_degrees
            or abs(pose["pitch"]) > cfg.face_max_pitch_degrees
            or abs(pose["roll"]) > cfg.face_max_roll_degrees
        ):
            warnings.append(_warning("HIGH_HEAD_ROTATION", "The head is turned or tilted. Face the camera directly for best results."))
        if k:
            warnings.append(_warning("IMAGE_ROTATED_FOR_DETECTION", f"The photo appeared sideways and was rotated {90 * k} degrees."))

        # A cheek on the side turned away from the camera is foreshortened: compare the projected
        # distance from the nose tip to each face edge (a landmark ratio, so no pose sign convention).
        nose = pixels[REGIONS["nose_tip"].landmark_indices[0]]
        left = float(np.linalg.norm(pixels[REGIONS["left_face_edge"].landmark_indices[0]] - nose))
        right = float(np.linalg.norm(pixels[REGIONS["right_face_edge"].landmark_indices[0]] - nose))
        hidden_side = None
        if min(left, right) < cfg.face_min_side_width_ratio * max(left, right):
            hidden_side = "left_cheek" if left < right else "right_cheek"

        for name in AREA_REGIONS:
            region = regions[name]
            region["visible"] = region["in_frame_ratio"] >= cfg.face_min_in_frame_ratio and name != hidden_side
            if not region["visible"]:
                label = name.replace("_", " ")
                message = f"The {label} is not clearly visible, so it will be excluded from skin analysis."
                warnings.append(_warning("REGION_NOT_VISIBLE", message))
        return warnings


_analyzer: FaceAnalyzer | None = None
_analyzer_lock = threading.Lock()


def get_face_analyzer() -> FaceAnalyzer:
    """Process-wide analyzer, created on first use (model load takes about 1 s)."""
    global _analyzer
    with _analyzer_lock:
        if _analyzer is None:
            _analyzer = FaceAnalyzer()
        return _analyzer


def close_face_analyzer() -> None:
    global _analyzer
    with _analyzer_lock:
        if _analyzer is not None:
            _analyzer.close()
            _analyzer = None
