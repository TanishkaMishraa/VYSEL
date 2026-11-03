# Phase 4.5 — Background pipeline and evaluation

## Pipeline and frontend status

`POST /v1/images` validates and stores a consented selfie. `POST /v1/scans` creates a
persisted `queued` scan and enqueues `vysel.analyze_face_scan` in Celery, returning
`202 Accepted` and `Location: /v1/scans/{scan_id}`. The worker re-validates the stored
image, runs face detection/landmarks, skin analysis, face shape and facial attributes,
then persists the complete result. `GET /v1/scans/{scan_id}` is owner-scoped; it returns
`queued`, `running`, `succeeded` or `failed`. While work is pending it returns
`Retry-After: 1`. Worker errors are stored as safe actionable codes/messages; paths and
tracebacks remain in server logs. Celery retries a task after worker loss, and processing
is idempotent for terminal scan records.

The authenticated scan page uploads only after explicit consent and polls that scan URL.
It fills the estimate fields when the scan succeeds; users can edit those estimates or
continue manually if a field is unavailable. Uploaded source images and biometric scan
data retain the existing 24-hour expiry policy.

Run locally from `apps/api`:

```bash
celery -A app.worker worker --pool=solo --loglevel=INFO  # Windows
celery -A app.worker worker --loglevel=INFO              # Linux/macOS
```

In a second terminal, run the API using the existing setup. Set `CELERY_BROKER_URL` to
Redis DB 1 and `CELERY_RESULT_BACKEND` to Redis DB 2, as in `.env.example`. Tests set
`CELERY_TASK_ALWAYS_EAGER=true`; production and normal development must use a worker.

## Evaluation data status

The repository does not contain a representative consented dataset. No accuracy, fairness,
or demographic performance claim is made. Do not populate the test split with synthetic or
public celebrity images and describe it as representative. Synthetic fixtures test pipeline
behavior only; they cannot measure real-world generalization or fairness.

Use the CSV headers in `evaluation/*.template.csv` with the corresponding evaluation script.
Collect images only with explicit informed consent for biometric processing and evaluation. Keep the image
files and manifest in access-controlled storage outside Git. Use pseudonymous person IDs;
never put names, email addresses, or direct identifiers in the manifest. Record consent and
retention separately in the approved study records, not in Git. Delete data at the agreed
retention deadline.

### Sampling and labels

- Recruit enough distinct people to represent varied skin tones, age bands, genders where
  appropriate, camera quality, image sizes, lighting/exposure, blur, glasses, facial hair,
  hairstyles/head coverings, pose, occlusion, no-face and multi-face cases. Set targets before
  recruitment and report actual counts and missing groups.
- Assign each person, and all their images, to exactly one split: validation or test. Keep
  test labels sealed until thresholds and settings are frozen. The evaluation scripts reject
  identity leakage across splits.
- Have trained annotators label face count/presence, landmark points and region masks where
  applicable; independent raters label subjective face shape, eye colour, hair colour, and
  image suitability. Adjudicate disagreements and report inter-rater agreement. Annotators
  should not see model output before labeling.
- Record privacy-reviewed group labels in `groups` (for example `monk_tone=6;lighting=low`)
  and report per-group sample sizes. Do not infer demographic identity from the image.

### Metrics and commands

Run on validation to debug and tune. The scripts report classification precision/recall,
macro-F1, confusion matrices, availability/coverage, and subgroup results. The face evaluator
also reports detection and landmark/region metrics; image validation reports false acceptance
and false rejection rates. Attribute evaluation reports mean, median, p95 processing time and
throughput per image. Timing includes image decode and the face plus appearance pipeline, but
excludes API/network and queue wait; measure those separately in a deployed load test.

```bash
python scripts/evaluate_images.py /secure/manifest.csv /secure/images
python scripts/evaluate_faces.py /secure/manifest.csv /secure/images
python scripts/evaluate_skin.py /secure/manifest.csv /secure/images
python scripts/evaluate_attributes.py /secure/manifest.csv /secure/images --output validation-report.json
```

Fit prototypes or tune thresholds using validation only. Freeze configuration and model
artifacts, then run each script once with its held-out test option. Attribute example:

```bash
python scripts/evaluate_attributes.py /secure/manifest.csv /secure/images --evaluate-test --output test-report.json
```

Report the dataset composition, consent/retention process, split counts, label agreement,
all overall and subgroup metrics with confidence intervals, unavailability/failure rates,
processing-time percentiles, software/model versions, and threshold settings. Treat small
subgroups as inconclusive, not as evidence of parity. Accuracy/fairness results remain pending
until this protocol has been run on that real dataset.
