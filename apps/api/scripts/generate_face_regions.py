"""Derive facial-region landmark indices from MediaPipe's documented topology.

Inputs (both published by MediaPipe, nothing hand-picked):
  * the documented connection sets in `mediapipe.tasks.python.vision.FaceLandmarksConnections`
    (face oval, eyes, eyebrows, nose, lips, tessellation), and
  * the canonical face model (`canonical_face_model.obj`, 468 vertices, y up, +x = subject's left),
    vendored at tests/fixtures/mediapipe/canonical_face_model.obj.

Each region is a set of mesh vertices selected by its position relative to those documented
anchors in the canonical (frontal, neutral) face, with a margin expressed as a fraction of the
interocular distance so the rule is scale-free and not tuned to any photographed face.

    python scripts/generate_face_regions.py            # print the generated module
    python scripts/generate_face_regions.py --write    # rewrite app/services/face_region_data.py

tests/test_face_regions.py regenerates this output and fails if the committed module drifts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

API_DIR = Path(__file__).resolve().parents[1]
CANONICAL_OBJ = API_DIR / "tests" / "fixtures" / "mediapipe" / "canonical_face_model.obj"
OUTPUT = API_DIR / "app" / "services" / "face_region_data.py"

# Margin between a region and the documented feature it borders, as a fraction of the
# canonical interocular distance (eye-centre to eye-centre). Geometric, not data-tuned.
MARGIN_FRACTION = 0.08


def load_canonical(path: Path = CANONICAL_OBJ) -> np.ndarray:
    vertices = [[float(n) for n in line.split()[1:4]] for line in path.read_text().splitlines() if line.startswith("v ")]
    return np.asarray(vertices)


def _indices(connections) -> list[int]:
    return sorted({i for c in connections for i in (c.start, c.end)})


def _ordered_ring(connections) -> list[int]:
    """Walk a closed contour given as an unordered list of edges."""
    neighbours: dict[int, list[int]] = {}
    for c in connections:
        neighbours.setdefault(c.start, []).append(c.end)
        neighbours.setdefault(c.end, []).append(c.start)
    start = min(neighbours)
    ring, previous, current = [start], None, start
    while True:
        nxt = next(n for n in neighbours[current] if n != previous)
        if nxt == start:
            return ring
        ring.append(nxt)
        previous, current = current, nxt


def derive_regions(vertices: np.ndarray) -> dict[str, list[int]]:
    from mediapipe.tasks.python.vision import FaceLandmarksConnections as C

    x, y = vertices[:, 0], vertices[:, 1]
    oval = _ordered_ring(C.FACE_LANDMARKS_FACE_OVAL)
    left_eye, right_eye = _indices(C.FACE_LANDMARKS_LEFT_EYE), _indices(C.FACE_LANDMARKS_RIGHT_EYE)
    brows = _indices(C.FACE_LANDMARKS_LEFT_EYEBROW) + _indices(C.FACE_LANDMARKS_RIGHT_EYEBROW)
    nose, lips = _indices(C.FACE_LANDMARKS_NOSE), _indices(C.FACE_LANDMARKS_LIPS)

    interocular = float(np.linalg.norm(vertices[left_eye].mean(0) - vertices[right_eye].mean(0)))
    margin = MARGIN_FRACTION * interocular

    # Keep skin regions off the face boundary: exclude the oval and its 1-ring neighbours.
    adjacency: dict[int, set[int]] = {}
    for c in C.FACE_LANDMARKS_TESSELATION:
        adjacency.setdefault(c.start, set()).add(c.end)
        adjacency.setdefault(c.end, set()).add(c.start)
    boundary = set(oval) | {n for i in oval for n in adjacency[i]}
    features = set(left_eye) | set(right_eye) | set(brows) | set(nose) | set(lips)
    interior = [i for i in range(len(vertices)) if i not in boundary and i not in features]

    brow_top = y[brows].max()
    eye_bottom = min(y[left_eye].min(), y[right_eye].min())
    nose_half_width = np.abs(x[nose]).max()
    mouth_corner_y = y[lips][np.argmax(np.abs(x[lips]))]
    lips_bottom = y[lips].min()
    mouth_half_width = np.abs(x[lips]).max()
    nose_bottom = y[nose].min()

    def cheek(side: int) -> list[int]:
        return [i for i in interior if side * x[i] >= nose_half_width + margin and mouth_corner_y <= y[i] <= eye_bottom - margin]

    def nearest_on_oval(side: int, level: float) -> int:
        candidates = [i for i in oval if side * x[i] > 0]
        return min(candidates, key=lambda i: abs(y[i] - level))

    # Jawline: the contiguous lower arc of the oval (below the base of the nose), ordered from
    # the subject's right ear through the chin to the left ear.
    first_upper = next(k for k, i in enumerate(oval) if y[i] > nose_bottom)
    rotated = oval[first_upper:] + oval[:first_upper]
    jawline = [i for i in rotated if y[i] <= nose_bottom]
    if x[jawline[0]] > 0:
        jawline.reverse()

    return {
        "face_oval": oval,
        # The mesh ends below the hairline, so the upper oval arc is still forehead skin; only
        # the eyebrows are excluded. Coverage is limited to what the mesh models.
        "forehead": [i for i in range(len(vertices)) if y[i] >= brow_top + margin and i not in features],
        "left_cheek": cheek(+1),
        "right_cheek": cheek(-1),
        "chin": [i for i in range(len(vertices)) if y[i] <= lips_bottom - margin and abs(x[i]) <= mouth_half_width],
        "jawline": jawline,
        # Single reference points for face-shape measurements.
        "forehead_top": [max(oval, key=lambda i: y[i])],
        "chin_bottom": [min(oval, key=lambda i: y[i])],
        "nose_tip": [max(nose, key=lambda i: vertices[i, 2])],  # most forward nose vertex (+z faces camera)
        "left_face_edge": [max(oval, key=lambda i: x[i])],
        "right_face_edge": [min(oval, key=lambda i: x[i])],
        "left_jaw_angle": [nearest_on_oval(+1, mouth_corner_y)],
        "right_jaw_angle": [nearest_on_oval(-1, mouth_corner_y)],
        "left_forehead_edge": [nearest_on_oval(+1, brow_top)],
        "right_forehead_edge": [nearest_on_oval(-1, brow_top)],
    }


def derive_features() -> dict[str, list[int]]:
    """Eye contours and irises: MediaPipe's documented sets, walked into ordered rings.

    The iris centre is the one iris landmark (468-477) that is not on its documented ring; each
    iris block is centre + 4 ring points, so it is the index just before the ring.
    """
    from mediapipe.tasks.python.vision import FaceLandmarksConnections as C

    features: dict[str, list[int]] = {}
    for side in ("left", "right"):
        features[f"{side}_eye"] = _ordered_ring(getattr(C, f"FACE_LANDMARKS_{side.upper()}_EYE"))
        ring = _ordered_ring(getattr(C, f"FACE_LANDMARKS_{side.upper()}_IRIS"))
        centre = min(ring) - 1
        if not (468 <= centre < 478 and centre not in ring):
            raise ValueError("Unexpected MediaPipe iris topology")
        features[f"{side}_iris"] = ring
        features[f"{side}_iris_center"] = [centre]
    return features


def render_module(regions: dict[str, list[int]], features: dict[str, list[int]]) -> str:
    lines = [
        '"""GENERATED by scripts/generate_face_regions.py. Do not edit by hand.',
        "",
        "Landmark indices per facial region, derived from MediaPipe's documented connection sets",
        "and canonical face model. Left/right are the subject's own left/right.",
        '"""',
        "",
        "REGION_LANDMARKS: dict[str, tuple[int, ...]] = {",
    ]
    for name, indices in regions.items():
        lines.append(f'    "{name}": {tuple(indices)!r},')
    lines += ["}", "", "# Eye contours (ordered rings) and irises (ring + centre), for eye-colour sampling."]
    lines.append("FEATURE_LANDMARKS: dict[str, tuple[int, ...]] = {")
    for name, indices in features.items():
        lines.append(f'    "{name}": {tuple(indices)!r},')
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help=f"write {OUTPUT.relative_to(API_DIR)}")
    args = parser.parse_args()
    module = render_module(derive_regions(load_canonical()), derive_features())
    if args.write:
        OUTPUT.write_text(module, encoding="utf-8")
        print(f"Wrote {OUTPUT}")
    else:
        print(module, end="")


if __name__ == "__main__":
    main()
