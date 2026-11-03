# Skin colour and undertone (Phase 4.3)

Every successful face scan (`POST /v1/scans`, see [FACE_ANALYSIS.md](FACE_ANALYSIS.md)) now also
estimates skin tone and undertone from the cheeks, forehead and chin found in Phase 4.2. The
result is in the scan's `skin` block. Both values are **preliminary estimates**. Their confidences
are heuristic and uncalibrated until the evaluation below has been run on real, consented data.

## Output

```jsonc
"skin": {
  "status": "ok",                                   // or "unavailable" + error {code, message}
  "skin_tone": {
    "hex": "#D09D7E", "lab": {"l": 68.9, "a": 14.9, "b": 23.6},
    "depth": "medium",                              // contract SkinDepth: fair|light|medium|tan|deep
    "confidence": 0.69, "label": "estimate",
    "ita_degrees": 38.7, "ita_category": "intermediate",
    "monk": {"value": 5, "hex": "#D7BD96", "delta_e": 11.8}
  },
  "undertone": {
    "value": "neutral",                             // warm | cool | neutral
    "confidence": 0.68, "label": "estimate", "method": "cielab-hue-v1",
    "hue_angle": 57.8, "chroma": 27.9, "reference_hue": 55.0, "delta_h": 1.37
  },
  "color_correction": {"method": "shades_of_gray", "gains": {"r": 0.98, "g": 1.02, "b": 1.0},
                       "clamped": false, "applied": true, "reference_pixels": 763237},
  "clusters": [{"lab": {…}, "hex": "#D19B7B", "share": 0.42, "used": true}, …],
  "regions": {"left_cheek": {"used": true, "pixels": 1965, "lab": {…}, "hex": "…", "delta_e_from_consensus": 1.7},
              "right_cheek": {"used": false, "reason": "color_inconsistent", "pixels": 2104}, …},
  "pixels_used": 9039,
  "warnings": [{"code": "STRONG_COLOR_CAST", "message": "…"}]
}
```

If no usable skin is visible, the face scan still succeeds and `skin` is `{"status": "unavailable"}`
with one of these codes:
- `NO_VISIBLE_SKIN`: every region is hidden, out of frame or too small.
- `INSUFFICIENT_SKIN_PIXELS`: fewer than 300 clean pixels remain.

Warnings:
- `STRONG_COLOR_CAST`: the correction hit its limit.
- `WHITE_BALANCE_LIMITED`: little background is visible for estimating the light.
- `REGION_COLOR_INCONSISTENT`: a region was excluded or disagrees with the rest.
- `UNDERTONE_REGIONS_DISAGREE`
- `LOW_CONFIDENCE_UNDERTONE`

From Python: `analyze_skin(rgb, face_analysis, settings)` in `app/services/skin_analysis.py`.
Colour maths is in `app/services/color.py`.

## Method

1. **Colour correction.** Skin colour depends on the light. The illuminant is estimated with
   **Shades of Gray** (Minkowski p = 6; Finlayson & Trezzi, 2004) on pixels **outside** the face
   (the face oval enlarged 30%), so the person's own skin cannot pull the correction. It is
   corrected with von Kries gains in linear light. Gains are limited to 1/1.5–1.5; hitting the
   limit is reported. Exposure is deliberately **not** normalized, because brightening a photo
   would also make the skin look lighter.
2. **Skin pixels.** The visible Phase 4.2 area regions (forehead, both cheeks, chin) are filled
   and eroded by 3% of face width away from their edges. Clipped pixels are dropped, then per
   region any pixel more than 3 robust standard deviations (median/MAD of CIEDE2000 distance)
   from the region's median colour is dropped. This removes stray hair, glasses frames, shine and
   deep shadow. Each region contributes at most 6,000 pixels, so the large forehead doesn't
   dominate.
3. **Region consistency.** With three or more regions, a region whose median colour is more than
   10 CIEDE2000 from the consensus is excluded. This catches a hand, scarf, heavy shadow or makeup
   over that area. It addresses the occlusion limitation noted in Phase 4.2.
4. **KMeans** (`cv2.kmeans`, k = 3, k-means++, fixed seed) on the pooled CIELAB pixels separates
   shading bands. The skin colour is the share-weighted mean of the clusters, leaving out minor
   clusters (<15% share) far from the typical pixel. "Largest cluster only" was measured and
   rejected: which shading band is largest flips with k or with one region hidden, moving the
   estimate by up to 6 L* / 5.8 CIEDE2000 on the same face.
5. **Skin tone.**
   - **ITA°** = atan((L* − 50) / b*) (Chardon et al., 1991), categorized very light / light /
     intermediate / tan / brown / dark (>55, >41, >28, >10, >−30).
   - Mapped to the contract's `depth`: brown and dark both map to `deep`.
   - The nearest **Monk Skin Tone** swatch is found by CIEDE2000.
6. **Undertone.**
   - Measured from the CIELAB hue angle of the skin colour, relative to a neutral reference hue.
   - The difference is expressed as the perceptual hue difference ΔH (CIEDE units), positive =
     more yellow (warm) and negative = more pink/red (cool). Within ±2.5 ΔH it is neutral.
   - Because ΔH scales with chroma, low-chroma skin (very light or very deep), whose undertone is
     hardest to judge, falls toward neutral rather than being forced into warm or cool.
   - `olive`, allowed by the contract, is not produced by this method.

### Why the reference is configurable

- **Why not the Monk swatches?** Undertone methods easily end up measuring *depth* instead of
  undertone. The obvious reference, the Monk swatches, is unsuitable: their hue angles jump
  around (74°, 89°, 82°, 74°, 59°, 49°, 66°… from MST 1 to 10) because they are illustrative
  colours, not measured skin.
- **Constant starting point.** The default is a constant 55°, a starting value near the middle of
  the hue range typically reported for facial skin. **It is not tuned on any data.**
- **Fitted reference.** `scripts/evaluate_skin.py --fit-reference` fits a lightness-dependent
  reference from labelled-*neutral* validation images. Enable it with
  `SKIN_UNDERTONE_REFERENCE_PATH`.

### Confidence

The confidence values are heuristics, not calibrated probabilities:
- **Skin tone:** combines colour-correction size, pixel coverage, agreement between regions and
  the share of pixels in the clusters used.
- **Undertone:** starts from the distance to the nearest class boundary. It is penalized more
  heavily for colour correction (measured below: residual correction error moves hue by about the
  band's width) and capped at 0.3 when the correction hits its limit.

## Configuration

| Variable | Default | Rationale |
|---|---|---|
| `SKIN_WHITE_BALANCE` | `shades_of_gray` | or `none` |
| `SKIN_WB_MINKOWSKI_P` | 6 | Finlayson & Trezzi's recommended exponent |
| `SKIN_WB_MAX_GAIN` | 1.5 | Bounds the correction; larger casts are flagged, not "fixed" |
| `SKIN_MASK_EROSION_RATIO` | 0.03 | Keeps samples off region edges (brows, nose, hairline) |
| `SKIN_MIN_PIXELS` / `_PER_REGION` | 300 / 50 | Below this the estimate is noise |
| `SKIN_KMEANS_CLUSTERS` / `_SEED` | 3 / 0 | Highlight, mid, shadow bands; deterministic |
| `SKIN_REGION_MAX_DELTA_E` | 10 | CIEDE2000 10 is an obvious colour difference |
| `SKIN_UNDERTONE_REFERENCE_HUE` | 55 | Untuned starting point (see above) |
| `SKIN_UNDERTONE_NEUTRAL_DELTA_H` | 2.5 | A clearly noticeable hue difference; untuned |
| `SKIN_UNDERTONE_REFERENCE_PATH` | unset | Lightness-dependent reference fitted on validation |

## What has been measured

All numbers come from **one subject** (MediaPipe's test portrait) with controlled variations:
- a lighting cast is a per-channel gain in linear light;
- darker skin is a linear-light scale of the face;
- an undertone shift is an a*/b* offset.

They test whether the method behaves correctly. They are **not** accuracy or fairness results.

| Check (pytest) | Result |
|---|---|
| Colour maths vs references | sRGB→Lab within 0.01; CIEDE2000 matches 9 published pairs (Sharma et al., 2005) to 1e-4 |
| Tungsten / shade / green fluorescent cast (CIEDE2000 to the uncast skin) | 5.9 / 4.8 / 6.4 uncorrected → **0.8 / 1.9 / 1.2** corrected |
| Strong cast at the correction limit | 9.5 → 6.5, flagged `STRONG_COLOR_CAST`, undertone confidence capped at 0.3 |
| Undertone under the moderate casts | shade cast flips neutral → warm (residual error ≈ 2–3 ΔH ≈ the band width); confidence drops to ≈ 0.41–0.44 |
| Cheek covered by a scarf or a skin-coloured "hand" | region excluded; estimate moves 0.25 CIEDE2000 |
| Clipped forehead shine | pixels dropped; estimate moves < 2 |
| k = 2 / 3 / 4 clusters | estimate moves 0.0 / – / 1.6 CIEDE2000 |
| Skin darkened ×0.7 / 0.45 / 0.25 / 0.12 | L* 59 / 51 / 37 / 27 (monotonic); Monk 6 → 8; depth tan → deep; undertone stays neutral (ΔH 0.8–1.2) |
| a*/b* shifts: yellower / redder / pinker | warm / cool / cool |
| Speed | ≈ 125 ms per scan on a laptop CPU (after face detection) |

## Evaluation protocol (to do before any accuracy claim)

1. **Consent and data.** Participants consent to biometric processing for evaluation, with a
   retention period. Cover the full Monk range (aim for ≥ 30 people per Monk band, or merge
   adjacent bands), ages, genders, and a mix of devices, indoor and daylight lighting.
2. **Ground truth.**
   - *Skin tone:* a colorimeter or spectrophotometer reading of cheek skin (CIELAB D65), plus
     rater Monk labels.
   - *Undertone:* consensus of at least two trained raters under controlled daylight-balanced
     light, recorded **before** seeing the model's output. Report rater agreement (kappa);
     undertone is subjective, and the model cannot be held to more than the raters' own
     agreement.
3. **Splits.** Assign each person to validation or test only; the script refuses identity
   leakage.
4. **Run.**
   ```bash
   python scripts/evaluate_skin.py manifest.csv dataset/                          # validation
   python scripts/evaluate_skin.py manifest.csv dataset/ --sweep-band 1.5,2.5,3.5 --sweep-reference-hue 50,55,60
   python scripts/evaluate_skin.py manifest.csv dataset/ --fit-reference models/undertone_reference.json
   python scripts/evaluate_skin.py manifest.csv dataset/ --evaluate-test --output report.json   # once
   ```
   The report covers:
   - **Skin tone:** CIEDE2000 to the reference reading (mean, median, p90, share ≤ 5), ITA error,
     Monk exact / ±1 / MAE.
   - **Undertone:** accuracy, macro-F1, Cohen's kappa, the confusion matrix, per-class
     precision/recall, and accuracy when confidence ≥ 0.5 together with how many images that
     covers.
   - **Breakdown:** everything per group and **per Monk value**, so a method that confuses depth
     with undertone shows up. Groups with fewer than 30 people are flagged `conclusive: false`.
5. **Tuning.** Tune the band, the reference hue or a fitted reference on validation only, freeze
   them, then run the test split once.
6. **Fairness.** Treat a Monk band whose undertone metrics are clearly worse, or whose
   predictions skew toward one class, as a release blocker.

## Limitations

- **No calibration or measured accuracy yet.** Confidences are heuristics. Undertone labels are
  subjective even for experts.
- **Lighting.** A single global white-balance correction cannot fix mixed lighting, coloured light
  reflected onto the face (e.g. from a green wall), or strong casts beyond ±50% per channel.
  Without a colour reference card in the photo, undertone stays sensitive to lighting.
- **Background-based correction** assumes the scene averages to grey in the Shades-of-Gray sense.
  A frame filled with one strong colour biases it, which `WHITE_BALANCE_LIMITED` and the gain
  limit only partly guard against.
- **Camera processing** (beauty filters, aggressive tone mapping, HDR) changes skin colour before
  the analysis sees it.
- **Makeup, tan lines, redness, vitiligo, freckles and facial hair** affect the sampled colour.
  Region consistency removes clearly different regions, not subtle ones.
- **Depth buckets.** Mapping ITA's six categories onto the contract's five depths merges brown
  and dark into `deep`. The nearest Monk swatch can be far from the actual skin colour (11.8
  CIEDE2000 on the test portrait), because the swatches have lower chroma than much real skin.
- **Olive** undertones are not modelled.
