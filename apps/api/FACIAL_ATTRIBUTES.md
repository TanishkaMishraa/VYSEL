# Face shape and facial attributes (Phase 4.4)

Every successful face scan (`POST /v1/scans`) now also estimates:
- face shape from landmark geometry;
- eye colour;
- hair colour;
- feature contrast, the lightness difference between hair (or eyes) and skin.

It also returns these estimates in the exact input format of the recommendation engine. All
values are **estimates** with heuristic, uncalibrated confidences until the evaluation below has
been run on consented, labelled data.

Related: [FACE_ANALYSIS.md](FACE_ANALYSIS.md) (landmarks) and [SKIN_ANALYSIS.md](SKIN_ANALYSIS.md)
(skin tone, undertone and the shared colour correction).

## Output

```jsonc
"attributes": {
  "face_shape": {
    "status": "ok", "value": "oblong", "confidence": 0.66, "label": "estimate",
    "alternatives": [{"value": "oval", "confidence": 0.28}, {"value": "heart", "confidence": 0.05}],
    "method": "landmark-prototypes-v1",
    "measurements": {"length_ratio": 1.28, "forehead_ratio": 0.95, "jaw_ratio": 0.88, "chin_angle": 77.4},
    "features": {"length": 0.115, "forehead": 0.04, "jaw": 0.013, "chin": -5.8},
    "probabilities": {"oblong": 0.66, "oval": 0.28, …},
    "warnings": []
  },
  "eye_color":  {"status": "ok", "value": "dark_brown", "confidence": 0.6, "label": "estimate",
                 "hex": "#332521", "lab": {…}, "eyes": {"left": {"used": true, "pixels": 52, …}, "right": {…}}},
  "hair_color": {"status": "ok", "value": "black", "confidence": 0.64, "label": "estimate",
                 "hex": "#514D4A", "lab": {"l": 33.2, "a": 0.9, "b": 2.8}, "band_pixels": 4931, "background_delta_e": 19.6},
  "contrast":   {"value": "medium", "confidence": 0.49, "label": "estimate", "delta_l": 35.7, "source": "hair"}
},
"recommendation_features": {           // = schemas.RecommendationFeatures; POST it to /v1/recommendations or /v1/reports
  "face_shape": {"value": "oblong", "confidence": 0.66},
  "undertone":  {"value": "neutral", "confidence": 0.68},
  "skin_depth": {"value": "medium", "confidence": 0.69},
  "contrast":   {"value": "medium", "confidence": 0.49}
}
```

Each attribute can be `{"status": "unavailable", "error": {code, message}}` without failing the
scan:

| Attribute | Code | Meaning |
|---|---|---|
| Face shape | `FACE_NOT_FULLY_VISIBLE` | The face outline is cut off by the frame |
| Eye colour | `EYES_NOT_VISIBLE` | Irises too small (< 4 px radius), closed or covered |
| Hair colour | `HAIR_NOT_VISIBLE` | No hairline found (very short hair, shaved head, a covering, or hair too close to skin colour), or the top of the head is out of frame |
| Hair colour | `HAIR_NOT_SEPARABLE` | The hair's colour also fills the background |

`recommendation_features` is `null` when face shape or skin is unavailable. If contrast is
unavailable, the field is omitted and the engine uses its default.

## Face shape

1. **Measurements** use 3D landmark positions (x, y in pixels; MediaPipe's z on the same scale as
   x), so head tilt foreshortens them less than 2D distances would:
   - face length: mesh top (landmark 10) to chin (152), divided by cheekbone width (127–356);
   - forehead width (21–251) and jaw width (58–288), each divided by cheekbone width;
   - the chin angle between the two jaw angles, seen from the chin.

   The points come from the generated region definitions (see FACE_ANALYSIS.md).
2. **Features.** Each ratio is expressed as its log-deviation from the same ratio on MediaPipe's
   **canonical face model**, an average frontal face (chin angle in degrees). The canonical face is
   the zero point, so there are no hand-set absolute thresholds. The mesh ends below the hairline
   for everyone, so that quirk cancels out.
3. **Classification** is a Gaussian nearest-prototype rule. Each shape is a point that encodes its
   usual stylist description:
   - oblong: clearly longer than wide;
   - round: about as long as wide, with a wide soft chin;
   - square: jaw as wide as the cheekbones;
   - heart: wide forehead, narrow jaw, pointed chin;
   - diamond: cheekbones widest;
   - oval: a little longer than wide and balanced.

   Probabilities are softmax(−distance²/2) in units of a typical person-to-person spread. The
   canonical average face itself classifies as oval.
4. **Caveats.**
   - The prototypes and spreads are **starting values, not fitted to any labelled face**.
     `scripts/evaluate_attributes.py --fit-prototypes` fits class means and pooled spreads on
     validation data; enable them with `FACE_SHAPE_PROTOTYPES_PATH`.
   - A turned or tilted head (`HIGH_HEAD_ROTATION` from the face scan) lowers the confidence by
     30% and adds `FACE_SHAPE_POSE`.

### Why not a CNN

The brief asks to evaluate a CNN classifier *if suitable training data is available*. It is not:

- **The most-used public dataset** ([Kaggle, Niten Lama](https://www.kaggle.com/datasets/niten19/face-shape-dataset)):
  5,000 images of **female celebrities** in 5 classes (no diamond). The images are scraped photos
  of public figures, with no consent from the subjects for biometric processing. It covers one
  gender, the label source and inter-rater agreement are undocumented, and the same people appear
  many times, which leaks identity across splits unless the split is made by person.
- **Re-uploads** (for example a [Roboflow copy](https://universe.roboflow.com/kent-8hp9o/face-shape-daie5)
  tagged CC BY 4.0) carry a licence chosen by the uploader. That doesn't establish rights to the
  photographs or the subjects' consent.
- **Other sets** (e.g. a [7-class Kaggle set](https://www.kaggle.com/datasets/minhquangbui/face-shapes))
  have the same provenance problems.

Training on these would conflict with this project's consent rules (see Phase 4.1 and
`tests/fixtures/mediapipe/README.md`). It would also likely learn the datasets' demographics and
photo style rather than face geometry. **No CNN was trained.**

A CNN becomes worth evaluating only once all of these hold:
1. A consented dataset exists, with several thousand people covering all six shapes, genders,
   ages and the full Monk range.
2. At least two independent raters label each face, and their agreement is measured. The script
   reports it (`face_shape_rater_agreement`); a model can't be expected to beat the raters' own
   agreement.
3. The split is by person.
4. On the frozen test split, the CNN clearly beats both this landmark baseline and the
   majority-class baseline, with no worse per-group gaps.

Until then, the transparent geometric baseline is the safer choice, and its fitted prototypes are
the first thing to try on real data.

## Eye colour

1. **Iris circle:** centre and radius from MediaPipe's documented iris landmarks (the centre is the
   landmark before each 4-point ring; a test checks it sits at the ring's centre).
2. **Masking:**
   - keep the circle inside the limbus (90% radius), clipped by the eyelid contour (documented
     `LEFT_EYE` / `RIGHT_EYE`);
   - exclude the pupil (35% of the iris radius);
   - trim pixels below the 15th and above the 85th lightness percentile (lashes, shadow,
     catch-lights).
3. **Colour:** the white-balanced median CIELAB per eye. The two eyes are combined when within 15
   CIEDE2000; otherwise the eye with more pixels is used and `EYES_DIFFER` is raised (reflection,
   uneven light or heterochromia).
4. **Classification** (untuned boundaries):
   - chroma < 4 → gray (L* ≥ 40) or dark brown;
   - bluish hue (180–330°) → blue;
   - greenish hue (90–180°) → green;
   - otherwise by lightness: dark brown < 35 ≤ brown < 50 ≤ hazel.
5. **Confidence** grows with pixel count (irises in selfies are often only 50–100 pixels) and is
   capped at 0.85.

## Hair colour

1. **Find the hairline.**
   - Work in the face's own frame (up = chin → mesh top, so a tilted head works).
   - Walk up a central strip above the mesh top until most pixels differ from the **forehead's**
     skin colour by ≥ 8 CIEDE2000.
   - The forehead is used because it's the skin nearest the hairline and lit the same way. 8 sits
     above the within-face variation measured in Phase 4.3 (1.6–5.9 between regions).
   - No hairline within half a face-length → `HAIR_NOT_VISIBLE`.
2. **Sample** a band from the hairline up to 0.15 face-lengths, ±0.35 face-widths around the
   centre line.
3. **KMeans** (k = 3, seeded) splits the band. The hair is the **dominant cluster that isn't skin**.
4. **Background check.** That cluster must differ by ≥ 8 CIEDE2000 from the background, sampled
   far from the head and level with or above the temples, so clothing doesn't count. If it doesn't,
   the result is `HAIR_NOT_SEPARABLE`; the method never falls back to a smaller cluster.
5. **Classification** (untuned boundaries), applied in this order:
   - high-chroma hue outside 10–100° → `other` (dyed);
   - chroma < 6 → black / gray / white by lightness (35, 75): colour with no hue isn't "brown";
   - L* < 20 → black;
   - chroma ≥ 25 and hue < 60° → red (ginger, copper, auburn);
   - L* ≥ 55 and b* ≥ 12 → blonde;
   - otherwise dark brown / brown / light brown by lightness (32, 48).

**Development notes.** Each of these was found on the portrait fixture and fixed with a general
rule, not a threshold fitted to that photo:
- A first ring-shaped band hugging the face oval sampled mostly forehead skin, because the mesh
  stops mid-forehead. That led to the hairline search.
- A background reference that included clothing rejected black hair as "background" (the navy
  suit). That led to the "level with or above the temples" rule and to never falling back to a
  minor cluster.
- Achromatic salt-and-pepper hair was first labelled "brown". That led to the chroma-first rule.

## Contrast

|L*(hair) − L*(skin)| (eyes if hair is unavailable):
- < 20 → low;
- < 40 → medium;
- otherwise high.

These cut-offs are untuned. This is the `contrast` input the recommendation engine uses for
seasonal palettes.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `FACE_SHAPE_PROTOTYPES_PATH` | unset | Prototypes/spreads fitted on validation (`--fit-prototypes`) |
| `EYE_MIN_IRIS_RADIUS_PX` / `EYE_MIN_PIXELS` | 4 / 20 | Below this, eye colour is unavailable |
| `HAIR_MIN_PIXELS` | 500 | |
| `HAIR_SKIN_DELTA_E` | 8 | Hair vs forehead skin (see above) |
| `HAIR_BACKGROUND_DELTA_E` | 8 | Hair vs background |
| `CONTRAST_LOW_MAX_DELTA_L` / `CONTRAST_MEDIUM_MAX_DELTA_L` | 20 / 40 | Untuned |

## What has been measured

As in Phases 4.2 and 4.3, these numbers come from **one subject** (MediaPipe's test portrait) and
controlled edits of it. They test behaviour, not accuracy or fairness.

| Check (pytest) | Result |
|---|---|
| Canonical face | features 0; classified oval; reference ratios match the model |
| Each prototype point | classified as its own shape |
| Portrait | oblong 0.66 (oval 0.28): length/width 12% above the canonical face |
| Image stretched / squashed vertically 15% | length feature +/− > 0.08; P(oblong) up / down; widths unchanged |
| 20° head tilt | length, forehead and jaw features move < 0.04 (3D measurements) |
| Face cut by the frame | `FACE_NOT_FULLY_VISIBLE` |
| Portrait eyes | dark brown, both eyes agree |
| Irises painted blue / green / hazel | blue / green / hazel |
| Eyes covered; image at 25% size | `EYES_NOT_VISIBLE` |
| Portrait hair (short, salt-and-pepper) | black (achromatic) |
| Hair painted blonde / golden blonde / ginger / black / brown / gray / blue | blonde / blonde / red / black / brown / gray / other |
| Red hair against the portrait's red curtains | `HAIR_NOT_SEPARABLE` (not guessed) |
| Hair painted skin colour (shaved head) | `HAIR_NOT_VISIBLE` |
| 20° head tilt | hair still black/gray |
| Scan → `POST /v1/recommendations` | accepted by the strict schema; 200 |
| Speed | ≈ 225 ms per scan for skin + all attributes on a laptop CPU |

## Evaluation protocol (to do before any accuracy claim)

```bash
python scripts/evaluate_attributes.py manifest.csv dataset/                         # validation
python scripts/evaluate_attributes.py manifest.csv dataset/ --fit-prototypes models/face_shape.json
python scripts/evaluate_attributes.py manifest.csv dataset/ --evaluate-test --output report.json   # once
```

**Data:**
- labels from trained raters, made before seeing model output;
- a second independent face-shape rater (`face_shape_rater2`), because rater agreement is the
  ceiling;
- one person per split (the script refuses identity leakage);
- groups covering Monk tone, gender, age, glasses, facial hair, hairstyles and head coverings.

**The report covers:**
- per attribute: accuracy, the majority-class baseline, macro-F1, Cohen's kappa, per-class
  precision/recall, the confusion matrix, the share of images where the attribute was available,
  and accuracy when confidence ≥ 0.5 together with how many images that covers;
- rater agreement for face shape;
- everything broken down per group, with groups under 30 people flagged `conclusive: false`.

**Tuning.** Fit prototypes or change thresholds on validation only, freeze them, then run the test
split once. A group with clearly worse results is a release blocker.

## Limitations

- **Nothing is fitted or calibrated yet**, and the confidences are heuristics. Face-shape labels
  are subjective even between expert raters.
- **Face length** is measured to the top of the mesh, not the hairline, so forehead height doesn't
  count. A receding or very high hairline isn't modelled.
- **Hair:**
  - It is sampled just above the hairline. Long hair below the face, highlights and ombré aren't
    represented, and a hat or headscarf is reported as hair if it isn't skin-coloured.
  - Hair close to skin colour (some blondes on light skin, or light skin with a bright scalp) can
    be `HAIR_NOT_VISIBLE`.
  - Backgrounds that match the hair make it `HAIR_NOT_SEPARABLE`.
- **Eyes:** irises are small in selfies. Glasses glare, coloured contact lenses, makeup and strong
  catch-lights affect the colour. Light eye colours under warm light are easily confused (hazel vs
  green, gray vs blue).
- **Categories** are a simplified vocabulary. "Other" hair covers all dyed colours.
- **Undertone** still comes from Phase 4.3, with its lighting sensitivity. That carries into
  `recommendation_features`.
