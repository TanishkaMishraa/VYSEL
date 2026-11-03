# VYSEL recommendation rules — MVP

The recommendation engine is deterministic and explainable. It does **not** inspect
images or infer facial attributes. The authenticated `POST /v1/recommendations`
endpoint accepts upstream estimates with confidence values and combines them with
the signed-in user's saved profile preferences.

## Input and scope

The request supplies estimated face shape (`oval`, `round`, `square`, `heart`,
`oblong`, or `diamond`), undertone (`warm`, `cool`, `neutral`, or `olive`), skin
depth (`fair`, `light`, `medium`, `tan`, or `deep`), and feature contrast
(`low`, `medium`, or `high`). Each attribute includes a confidence from 0 to 1.
Contrast defaults to `medium` at 0.5 confidence if omitted.

The endpoint returns top-three picks for hair, eyewear, makeup, outfit colour, and
outfit cut, plus a five-colour seasonal palette. Every pick has a stable catalogue
ID, a plain-language rationale, budget tier, and ranking score. `POST /v1/reports`
uses the same rules and stores a snapshot against the signed-in account. Users may
provide thumbs-up/down feedback, download a formatted PDF generated in their
browser, or explicitly enable and later revoke a public share link. PDF generation
does not send report data to a third-party service. Reports contain no account
identity on the public view. A face scan (`POST /v1/scans`) returns estimates as
`recommendation_features`, ready to send to these endpoints (see
apps/api/FACIAL_ATTRIBUTES.md).

Users may enter estimates manually or use an authenticated face scan. An optional
photo preview in the report form remains local to the browser.

## Feature mapping

- **Face shape → hair and frames:** a small explicit catalogue maps each supported
  face shape to cuts and frame outlines, with a base fit score and a reason. These
  are optional styling conventions, not claims about attractiveness, fit, or
  suitability for a particular person.
- **Face shape → outfit cut:** maps to neckline suggestions only. It does not infer
  body shape or body measurements.
- **Undertone, skin depth → makeup:** ranks a small shade catalogue. Matching
  undertone/depth raises fit; conflicting undertones lower it. Neutral estimates
  can use neutral shades. Shades should be tried in natural light.
- **Undertone, contrast, depth → season and palette:** warm plus high contrast/deep
  maps provisionally to Autumn, other warm combinations to Spring; cool plus high
  contrast/deep maps to Winter, other cool combinations to Summer. Neutral/olive
  uses contrast first and depth as a tie-breaker. Seasonal colour is subjective,
  so reported confidence is capped at 0.70 and the result is explicitly provisional.
- **Goals, style, occasions → ranking:** catalogue tags are matched against saved
  `UserPreferences`. A matching goal/category, style, or occasion increases rank;
  no saved answer uses a neutral score, and a mismatch is a soft penalty.
- **Budget → ranking:** a candidate within the saved budget tier receives the full
  budget score; a higher tier receives a soft penalty instead of being hidden.
  Missing budget leaves candidates neutral.

## Ranking

Each pick score is clamped to `[0, 1]` and the category returns up to three picks,
ordered by score (stable ID breaks ties):

```text
score = 0.50 × feature_fit
      + 0.20 × goal_match
      + 0.10 × personal_style_match
      + 0.10 × occasion_match
      + 0.10 × budget_match
```

For feature-based picks, `feature_fit` moves from neutral (`0.5`) toward the
catalogue's face-shape or tone fit by the relevant estimate confidence. Lower
confidence therefore weakens the effect of an estimate instead of treating it as
certain. Palette confidence is further capped at `0.70` because the season mapping
is a subjective heuristic.

For preference dimensions, a match scores `1.0`, a mismatch `0.45` (goals:
`0.35`), and a missing preference `0.65`. Budget match scores `1.0`, over-budget
scores `0.2`, and missing budget scores `0.65`. These are version-one product
heuristics, not empirically validated accuracy or effectiveness measurements.

The response carries the score weights and a disclaimer. Keep the estimates,
reasons, and subjective/optional nature visible in any UI that presents the picks.

## Product listings

`GET /v1/reports/{report_id}/products` matches saved report recommendations to a
small local India-focused product catalogue. Makeup matches require the same product
type and a nearby shade colour; hair tools and eyewear require an explicit style tag;
clothing matches use the suggested neckline or a nearby catalogue colour. A missing
match stays empty rather than being replaced with an unrelated item.

The catalogue includes retailer search links and indicative INR reference prices.
Prices, variants, stock and availability are not fetched live and may change; confirm
them with the retailer. The `budget` query filter uses the saved profile budget by
default (`low` up to ₹500, `mid` up to ₹1,500, `high` without a ceiling); `all`
removes the ceiling. This is a curated discovery catalogue, not an affiliate or
retailer partnership.

## Report history and deletion

Saved Style DNA reports are the durable history; `/v1/reports` lists them newest
first. Face scan rows include biometric landmarks and remain subject to the existing
short retention window rather than being exposed as durable history. The dashboard
loads two account-owned reports for side-by-side comparison.

`DELETE /v1/me` removes the account's preferences, auth tokens, reports, feedback,
saved looks, face scans, image metadata and private selfie files. If a private file
cannot be deleted, the API reports an error and leaves the account active so the
user can retry.
