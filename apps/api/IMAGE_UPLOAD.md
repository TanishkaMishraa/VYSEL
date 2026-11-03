# Selfie upload (Phase 4.1)

## Endpoint

`POST /v1/images` requires `Authorization: Bearer <access-token>` and a multipart body
with `file`, `consent=true`, and `policy_version`. Accepted JPG/JPEG/PNG files up to 5 MiB
return `201` with an opaque `img_...` ID, dimensions, size, expiration, and per-check quality
results. Quality failures return 422 problem+json with per-check errors. File type/corruption,
empty files, oversize uploads, missing auth, and missing consent return safe problem+json errors.
`GET /v1/images/{image_id}` returns metadata only and is scoped to the owning user.
`DELETE /v1/images/{image_id}` immediately removes the private file and metadata.

## Setup and storage

Install API dependencies with `pip install -r requirements.txt`, and apply the migration from
`apps/api` with `alembic upgrade head`. Configure `SELFIE_STORAGE_DIR` to a directory outside
the public web root. The default is `apps/api/.private/selfies`. Files are written with random
opaque storage keys using exclusive creation; submitted filenames never form a path. Metadata
records the owner, consent policy version, dimensions, quality checks, and a 24-hour expiration.
Run `python scripts/cleanup_expired_images.py` daily as a scheduled task to delete expired
image objects and rows. Account deletion also removes the owner's local image files.

## Threshold evaluation

Defaults are starting operational thresholds, not measured model accuracy. No representative
labeled selfie dataset ships with the repository. Create a consented private dataset covering
lighting, skin tones, cameras, image sizes and quality. Split by person into validation and test
sets; tune thresholds on validation only, freeze them, then evaluate test once. Manifest CSV
columns: `path,label,split,group`; labels are `suitable` or `unsuitable` and groups should be
privacy-reviewed quality/demographic group labels.

From `apps/api`, run:

```bash
python scripts/evaluate_images.py path/to/manifest.csv path/to/private-dataset
python scripts/evaluate_images.py path/to/manifest.csv path/to/private-dataset --blur-sweep 20,35,50 --brightness-sweep 25,35,45
python scripts/evaluate_images.py path/to/manifest.csv path/to/private-dataset --evaluate-test
```

The report contains confusion matrix, precision, recall, false acceptance/rejection rates, and
per-group error counts. Repeat threshold sweeps against validation only; retain consent and
delete dataset images according to the agreed retention policy. No accuracy is claimed until
this evaluation is performed on representative labeled data.
