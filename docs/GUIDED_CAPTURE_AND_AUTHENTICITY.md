# Guided capture and image authenticity

## Guided capture

The scan page's **Use guided camera** flow requests the front camera only after the user activates it. Camera access requires HTTPS (or localhost) and browser permission. The video frames and MediaPipe landmark inference stay in the browser; only a still JPEG is uploaded after the movement prompts pass and the user separately consents to selfie analysis.

The guide measures normalized facial landmark geometry for yaw (left/right turn), pitch (up/down), and roll (sideways tilt). It asks the user to look straight, completes four randomized directional prompts, and asks them to face straight again before capture. It rejects frames with no face, multiple faces, an off-center/too-small/too-large face, excessive roll, poor sampled exposure, or a soft low-resolution preview. The uploaded still is then subject to the API's existing full-resolution image and face checks.

Angle limits are configurable in the web build environment:

| Variable | Default | Meaning |
| --- | ---: | --- |
| `NEXT_PUBLIC_FACE_GUIDE_YAW_DEGREES` | 9 | Minimum relative yaw change for a turn prompt |
| `NEXT_PUBLIC_FACE_GUIDE_PITCH_DEGREES` | 4 | Minimum relative pitch change for a tilt prompt |
| `NEXT_PUBLIC_FACE_GUIDE_ROLL_DEGREES` | 12 | Maximum sideways tilt while capturing |

Values outside `(0, 45]` fall back to the defaults. These are starting geometric thresholds, not thresholds tuned on a representative demographic validation set. The browser preview exposure and sharpness checks are inexpensive guidance heuristics; server-side validation remains authoritative.

## Result interpretation and limitations

The results panel keeps face alignment, uploaded-image checks, and lighting checks separate. The existing scan pipeline estimates appearance and uses shades-of-gray white balance for skin analysis. This normalization helps reduce scene color-cast effects; it does not identify a camera brand, prove a filter was used, or determine whether an edit was intentional.

VYSEL currently has no validated beauty-filter, face-reshaping, face-swap, image-compositing, AI-generated-image, or presentation-attack detector. Those result categories are therefore **Inconclusive**. The randomized head movement check improves capture guidance but is not liveness proof: a replay or other presentation attack may satisfy it. Reference-image identity similarity is not part of this scan flow. No authenticity confidence score is reported.

Before using the movement check for identity or access decisions, collect a consented dataset spanning camera models, lighting, skin tones, face coverings, and accessibility needs. Tune thresholds on a validation split, keep a separate test split, and measure completion and rejection rates by relevant groups. Separately evaluate presentation attacks with a validated anti-spoofing model and an authorized, representative attack dataset. Do not treat the current heuristic as a security control.

## Manual device check

1. Start the web and API as described in the repository README and sign in.
2. Open **New scan**, choose **Use guided camera**, and grant camera permission.
3. Confirm the preview and face outline render; test straight, left, right, up, and down movements, then face forward again.
4. Check that dark/bright or soft preview guidance blocks capture and improves when conditions change.
5. Capture, provide selfie-processing consent, and verify the scan status and separate results assessments.
6. Retry the prompts and cancel the dialog; verify camera indicators turn off after capture/cancel and on component unmount.
7. Repeat in desktop and mobile browsers over HTTPS. Browser camera permissions, front-camera mirroring, and device exposure vary; this repository build does not replace physical-device verification.
