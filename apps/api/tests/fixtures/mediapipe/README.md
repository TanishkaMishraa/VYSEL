# MediaPipe regression fixtures

Fixed inputs for the face detection and landmark tests (`tests/test_face_*.py`, `tests/test_scans.py`).

| File | Source | Used for |
|---|---|---|
| `portrait.jpg` | MediaPipe test asset (`storage.googleapis.com/mediapipe-assets/portrait.jpg`) | one-face, rotation, tilt, low-resolution, occlusion, crop and aspect-ratio cases (derived in the tests) |
| `portrait_rotated.jpg` | MediaPipe test asset | sideways face without EXIF orientation |
| `cat.jpg` | MediaPipe test asset | no-face case |
| `portrait_expected_face_landmarks.pbtxt` | MediaPipe test asset | MediaPipe's published expected landmarks for `portrait.jpg`; checked with MediaPipe's own tolerance (0.03) |
| `canonical_face_model.obj` | `mediapipe/modules/face_geometry/data/` in the MediaPipe repository | input to `scripts/generate_face_regions.py` |

MediaPipe is licensed under Apache 2.0 (Copyright Google LLC). These files are unchanged copies.

## Consent and limits

The portrait is the subject of MediaPipe's own published test suite and appears to be a
public-domain official portrait. VYSEL holds no consent record for it, and one face cannot show
how the system performs across skin tones, ages, genders, poses or cameras. These fixtures pin
the pipeline's behaviour (regression); they are **not** an evaluation set, and no accuracy claim
is based on them.

Add fixtures from team volunteers only with written consent covering storage in this repository
and use in automated tests, and record that consent outside the repository. Measured
evaluation uses a private consented dataset; see `FACE_ANALYSIS.md`.
