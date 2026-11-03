# Face detection and landmarks (Phase 4.2)

Scans also include skin tone and undertone (Phase 4.3); see [SKIN_ANALYSIS.md](SKIN_ANALYSIS.md).

A selfie that passed Phase 4.1 validation is checked for **exactly one face**. MediaPipe's
478 face landmarks are extracted and mapped to the facial regions that skin analysis and
face-shape classification need: cheeks, forehead, chin, jawline, face oval and key points.

## Setup

```bash
cd apps/api
python scripts/setup_face_analysis.py          # installs MediaPipe (--no-deps) and downloads the model
python scripts/setup_face_analysis.py --check  # verify only
```

`start.ps1` and `start.sh` run this on every start. The model is MediaPipe's pretrained
`face_landmarker.task` (float16, v1) from Google's model storage. It is pinned by SHA-256
(`MODEL_SHA256` in `app/services/face_analysis.py`) and the API refuses any other file. It lives
in `apps/api/models/`, which is git-ignored. No model is trained or fine-tuned.

## API

Both endpoints need `Authorization: Bearer <access token>` and only see the caller's own data.

```http
POST /v1/scans            {"image_id": "img_..."}     -> 202 queued scan (Location: /v1/scans/scn_...)
GET  /v1/scans/{scan_id}                              -> 200 scan
```

`POST` queues the full pipeline in Celery. Poll the returned scan URL; it reports `queued`,
`running`, `succeeded` or `failed`, with `Retry-After: 1` while pending. Before analysis,
the worker re-validates the stored image with the current Phase 4.1 rules. The scan page polls
this endpoint and fills estimate fields when analysis succeeds. See
[PIPELINE_EVALUATION.md](PIPELINE_EVALUATION.md) for worker setup and evaluation protocol.

| Status | `code` | When |
|---|---|---|
| 202 | ? | Scan accepted; poll for a terminal status |
| `failed` | `NO_FACE_DETECTED` | No face was detected |
| `failed` | `MULTIPLE_FACES_DETECTED` | More than one face was detected |
| `failed` | `FACE_LANDMARKS_NOT_FOUND` | Detector found a face but could not place landmarks |
| `failed` | `IMAGE_QUALITY_FAILED`, `CORRUPT_IMAGE`, ... | Stored image failed Phase 4.1 re-validation |
| 404 | `NOT_FOUND` | Unknown image/scan, or owned by another user |
| 410 | `UPLOAD_EXPIRED` | Image past its 24 h retention, or its file is gone |
| 429 | `RATE_LIMITED` | More than 30 scans per user per 10 minutes |
| `failed` | `FACE_ANALYSIS_UNAVAILABLE` | MediaPipe/model unavailable (details only in server logs) |

Errors are `application/problem+json`. Responses never contain file paths, storage keys, stack
traces or internal IDs beyond the `img_`/`scn_` IDs the caller already has.

### Scan JSON

```jsonc
{
  "id": "scn_…", "image_id": "img_…", "status": "succeeded", "face_count": 1,
  "detection": {"confidence": 0.92, "bounding_box": {"x": 283, "y": 115, "width": 234, "height": 234}},
  "image": {"width": 820, "height": 1024, "orientation_corrected": false, "rotation_applied_degrees": 0},
  "landmarks": {"count": 478, "topology": "mediapipe-face-mesh-478", "coordinate_space": "…",
                "points": [{"index": 0, "x": 0.4966, "y": 0.2507, "z": -0.0123, "px": 407.2, "py": 256.7}, …]},
  "regions": {
    "left_cheek": {"kind": "area", "landmark_indices": […], "polygon": [[x, y], …], "area_px": 3120.5,
                   "bounding_box": {…}, "centroid": [x, y], "in_frame_ratio": 1.0, "visible": true},
    "forehead": {…}, "right_cheek": {…}, "chin": {…},
    "jawline":  {"kind": "contour", "polyline": [[x, y], …], "closed": false, …},
    "face_oval": {"kind": "contour", "closed": true, …}
  },
  "key_points": {"forehead_top": {"index": 10, "x": …, "y": …, "px": …, "py": …}, "chin_bottom": …, "nose_tip": …,
                 "left_face_edge": …, "right_face_edge": …, "left_jaw_angle": …, "right_jaw_angle": …},
  "head_pose": {"pitch": 3.9, "yaw": 1.8, "roll": 0.9},
  "warnings": [{"code": "FACE_LOW_RESOLUTION", "message": "…"}],
  "validation": {"resolution": {"passed": true, …}, "blur": {…}, "brightness": {…}, "exposure": {…}},
  "model": {"name": "mediapipe-face-landmarker/float16/1"},
  "created_at": "…", "expires_at": "…"
}
```

- **Coordinates.** `x`, `y` are normalized by image width and height. They are not clamped, so
  they fall outside [0, 1] when the face leaves the frame. `z` is MediaPipe's relative depth on
  the same scale as `x` (smaller is closer). `px`, `py` are pixels. Everything refers to the
  EXIF-oriented image, i.e. as people see it.
- **Left/right** are always the subject's own. In an unmirrored photo, `left_cheek` is on the
  image's right.
- **Warnings** do not block the scan. Downstream phases should use them, for example by skipping
  regions with `visible: false`:
  `LOW_DETECTION_CONFIDENCE`, `FACE_LOW_RESOLUTION`, `FACE_PARTIALLY_OUT_OF_FRAME`,
  `HIGH_HEAD_ROTATION`, `IMAGE_ROTATED_FOR_DETECTION`, `REGION_NOT_VISIBLE`.

### Reuse from Python

```python
from app.services.face_analysis import FaceAnalyzer, FaceAnalysisError

with FaceAnalyzer() as analyzer:              # or get_face_analyzer() for the process-wide instance
    try:
        result = analyzer.analyze_bytes(jpeg_bytes)   # validate with Phase 4.1 first
    except FaceAnalysisError as exc:
        exc.code, exc.face_count
```

`app/services/face_regions.py` (`REGIONS`, `region_geometry`) has no MediaPipe dependency, so
downstream code can recompute region geometry from stored landmarks.

## How it works

1. **Orientation.** EXIF orientation is applied first.
2. **Counting faces.** MediaPipe's BlazeFace detector (bundled inside `face_landmarker.task`)
   provides boxes and confidence scores. The Face Landmarker also returns up to
   `FACE_MAX_FACES_COUNTED` faces. Boxes from both are merged when one covers at least half of
   the other, which removes the landmarker's occasional duplicate of the same face. The number of
   distinct faces decides the result.
3. **Trust.** Landmarks are used only when they overlap the detector's face. If the two models
   disagree, the result is `FACE_LANDMARKS_NOT_FOUND`, not guessed landmarks.
4. **Rotation search.** This runs only when the upright pass is unreliable: no face, confidence
   below `FACE_LOW_CONFIDENCE_WARNING`, or a face rolled more than 45°. The image is then re-run
   at quarter turns, and the most confident pass where detector and landmarks agree wins.
   Coordinates are mapped back to the original frame. This catches sideways photos without EXIF
   data and upside-down photos. On an upside-down portrait, the upright pass returned a weak false
   positive on the clothing instead of the face.
5. **Window search.** This runs only for images at least 1.5× longer than wide in which nothing
   was found. The detector shrinks the whole frame to 128 px, so a face in a panorama-like frame
   becomes too small to detect. Overlapping square windows are searched and faces are merged
   across windows.
6. **Head pose** comes from MediaPipe's facial transformation matrix. Roll is re-expressed in the
   original frame after a rotation search.

### Region definitions (no guessed indices)

`scripts/generate_face_regions.py` derives every region from MediaPipe's own published topology:

- the documented connection sets in `mediapipe.tasks.python.vision.FaceLandmarksConnections`
  (`FACE_OVAL`, eyes, eyebrows, `NOSE`, `LIPS`, `TESSELATION`), and
- MediaPipe's canonical face model `canonical_face_model.obj`, vendored in `tests/fixtures/mediapipe/`.

| Region | Rule in the canonical (frontal) face |
|---|---|
| `face_oval` | Documented `FACE_OVAL` contour, walked in order |
| `forehead` | Mesh vertices above the eyebrows (plus margin), excluding eyebrows. The mesh ends below the hairline. |
| `left_cheek`/`right_cheek` | Interior vertices beside the nose, below the eye, above the mouth corner. Away from the oval boundary. |
| `chin` | Vertices below the lower lip, within the mouth's width |
| `jawline` | Contiguous lower arc of the oval below the base of the nose, right ear → chin → left ear |
| key points | Extremes of the oval (top, bottom, widest), most forward nose vertex, oval points level with the mouth corners |

The margin is 8% of the canonical interocular distance. It is geometric and scale-free, and was
not tuned on any photograph. The generated `app/services/face_region_data.py` is committed, and
`tests/test_face_regions.py` fails if it drifts from the generator or from MediaPipe's topology.
At runtime, an area region's polygon is the convex hull of its landmarks, so it stays a valid
polygon under head rotation.

## Configuration

All settings live in `app/config.py` and can be overridden from `.env`. Defaults are MediaPipe's
documented defaults or geometric rationale. None were fitted to photos.

| Variable | Default | Rationale |
|---|---|---|
| `FACE_MIN_DETECTION_CONFIDENCE` | 0.5 | MediaPipe default |
| `FACE_MIN_PRESENCE_CONFIDENCE` | 0.5 | MediaPipe default |
| `FACE_MAX_FACES_COUNTED` | 4 | Enough to tell 1 from many |
| `FACE_LOW_CONFIDENCE_WARNING` | 0.7 | Warning, and triggers rotation search |
| `FACE_MIN_FACE_WIDTH_PX` | 128 | Half the landmark model's 256 px input. Smaller faces are upsampled more than 2×. |
| `FACE_MAX_INFERENCE_SIDE` | 1920 | Inference copy only. The models work on 128–256 px crops. |
| `FACE_ROTATION_SEARCH` | true | Sideways and upside-down photos |
| `FACE_MAX_YAW/PITCH/ROLL_DEGREES` | 25 / 20 / 20 | Warning only |
| `FACE_MIN_IN_FRAME_RATIO` | 0.95 | Share of a region's landmarks that must be inside the image |
| `FACE_MIN_SIDE_WIDTH_RATIO` | 0.5 | Cheek on the turned-away side is "not visible" below this projected-width ratio |

Change a threshold only after a sweep on the **validation** split of a consented dataset (below).

## Evaluation

### What has been measured

All numbers below come from **one subject**: MediaPipe's published test portrait, plus
conditions derived from it. They show pipeline correctness and robustness to image
transformations. They are **not** accuracy or fairness results, and cannot be.

| Check (pytest) | Result |
|---|---|
| Landmarks vs MediaPipe's published expected output for the portrait | max abs error 0.0056 (MediaPipe's own tolerance: 0.03) |
| Quarter turns (90/180/270°), mapped back | mean error ≈ 0 px (exact recovery via rotation search) |
| Tilt 15° / 20° / 30° | NME 0.006 / 0.006 / 0.013; roll estimated within 1.3° |
| Downscale 50% / 35% / 25% / 15% | NME 0.003 / 0.006 / 0.009 / 0.028, `FACE_LOW_RESOLUTION` raised |
| JPEG quality 8 + Gaussian blur | NME 0.010 |
| Mouth and chin occluded | upper-face NME 0.011 |
| Aspect ratios 2:1 to 6:1, and tall 1:3 | detected, NME ≤ 0.008 |
| No face (cat photo, noise texture) | `NO_FACE_DETECTED` |
| Two faces (side by side, stacked, far apart in a 4:1 frame) | `MULTIPLE_FACES_DETECTED`, `face_count` 2 |

NME = mean landmark distance / face width, against the landmarks of the unmodified image.

### Protocol for real accuracy numbers (still to do)

Collect a **consented** dataset. Each participant signs consent for biometric processing and
evaluation, with a retention period. It must cover: skin tones (e.g. Monk Skin Tone scale),
ages, genders where appropriate, frontal/tilted/rotated poses, glasses, facial hair, lighting,
camera quality, partial occlusion, no-face and multi-face images. Annotate a landmark subset
(suggested: 10, 33, 133, 362, 263, 4, 61, 291, 152, 127, 356, 58, 288) and region polygons in
pixels of the EXIF-oriented image. Assign every **person** to one split only; the script refuses
manifests that leak identities across splits.

```bash
python scripts/evaluate_faces.py manifest.csv dataset/                        # validation
python scripts/evaluate_faces.py manifest.csv dataset/ --sweep-confidence 0.3,0.5,0.7
python scripts/evaluate_faces.py manifest.csv dataset/ --evaluate-test --output report.json   # once
```

The report covers detection precision/recall/F1, single-face acceptance, multiple-face and
no-face rejection, landmark NME (bounding-box normalized), the share of landmarks within 0.05
and 0.10 NME, region IoU against annotated polygons, and the same metrics per group. Groups with
fewer than 30 people are flagged `conclusive: false`. Tune thresholds on validation only, freeze
them, then run the test split once. Treat a group whose metrics are clearly worse as a release
blocker, not a footnote.

The CLI shows why thresholds must be swept on data: on the fixtures, lowering the detection
confidence to 0.3 turns the cat photo into a false positive.

## Limitations and known failure cases

- **Occlusion is not detected here.** MediaPipe still predicts landmarks under hands, masks or
  hair, so a covered cheek is reported as visible. Phase 4.3 skin analysis catches clearly
  different-coloured regions (`REGION_COLOR_INCONSISTENT`) and leaves them out.
- **Forehead coverage** stops where the mesh stops, below the hairline. Fringes and hats are not
  detected.
- **Small faces.** BlazeFace short-range is built for faces within about 2 m of the camera.
  Small background faces may be missed, and if detected they count towards
  `MULTIPLE_FACES_DETECTED`. That rejection is deliberate, so another person's face is never
  analyzed. Window search only runs when no face was found at all.
- **Faces reflected in mirrors or printed on posters/screens** count as faces.
- **Extreme yaw** (profile views) produces unreliable landmarks. It is only flagged through
  `HIGH_HEAD_ROTATION` and cheek visibility.
- **Head-pose signs** follow MediaPipe's transformation matrix. Only magnitudes are used for
  warnings.
- **Untested across demographics.** There is no representative evaluation yet, so no claim about
  performance across skin tones, ages or genders can be made.
- **Python 3.11.** MediaPipe 1.2.0 ships a `py3-none` wheel. CI runs the whole suite on 3.11.
  Local development here ran on 3.13.
