/**
 * MediaPipe Face Mesh topology (478 landmarks, also used by FaceLandmarker).
 * "Left"/"right" are the SUBJECT's sides, as in MediaPipe's own naming.
 * Index reference: mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
 */

export interface Point {
  x: number;
  y: number;
}

/** Outer lip contour, clockwise from the right mouth corner. */
export const LIPS_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146];
/** Inner lip contour (the mouth opening) — cut out so teeth and tongue stay uncoloured. */
export const LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95];

/** Upper lash lines, outer corner → inner corner. */
export const RIGHT_EYE_UPPER = [33, 246, 161, 160, 159, 158, 157, 173, 133];
export const LEFT_EYE_UPPER = [263, 466, 388, 387, 386, 385, 384, 398, 362];

/** Apple of the cheek, where blush sits. */
export const RIGHT_CHEEK = 50;
export const LEFT_CHEEK = 280;

/** Widest points of the face (near the tragus) — the scale reference for every overlay. */
export const FACE_EDGE_RIGHT = 234;
export const FACE_EDGE_LEFT = 454;
export const RIGHT_EYE_OUTER = 33;
export const LEFT_EYE_OUTER = 263;

/** Normalised (0–1) landmarks → canvas pixels; mirror for a selfie-style preview. */
export function toPixels(landmarks: { x: number; y: number }[], width: number, height: number, mirror: boolean): Point[] {
  return landmarks.map((l) => ({ x: (mirror ? 1 - l.x : l.x) * width, y: l.y * height }));
}

export const dist = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
export const mid = (a: Point, b: Point): Point => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

export function faceWidth(pts: Point[]): number {
  return dist(pts[FACE_EDGE_RIGHT], pts[FACE_EDGE_LEFT]);
}

/** Head roll in radians (0 = level), from the outer eye corners. */
export function roll(pts: Point[]): number {
  const a = pts[RIGHT_EYE_OUTER];
  const b = pts[LEFT_EYE_OUTER];
  // Order-independent: mirroring swaps which corner is on the left of the canvas.
  const [l, r] = a.x <= b.x ? [a, b] : [b, a];
  return Math.atan2(r.y - l.y, r.x - l.x);
}

/**
 * Adaptive exponential smoothing: steady when the head is still (kills jitter),
 * responsive when it moves (no lag). A light version of the One-Euro filter idea.
 */
export class LandmarkSmoother {
  private prev: Point[] | null = null;

  constructor(
    private readonly still = 0.35,
    private readonly moving = 0.85,
  ) {}

  smooth(next: Point[], scale: number): Point[] {
    const prev = this.prev;
    if (!prev || prev.length !== next.length) return (this.prev = next);
    // Mean motion relative to face size decides how much to trust the new frame.
    let motion = 0;
    for (let i = 0; i < next.length; i += 8) motion += dist(prev[i], next[i]);
    motion /= Math.ceil(next.length / 8) * Math.max(scale, 1);
    const a = Math.min(this.moving, this.still + motion * 40);
    this.prev = next.map((p, i) => ({ x: prev[i].x + (p.x - prev[i].x) * a, y: prev[i].y + (p.y - prev[i].y) * a }));
    return this.prev;
  }

  reset() {
    this.prev = null;
  }
}
