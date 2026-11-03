/**
 * Canvas 2D makeup renderer. Every size is relative to face width, so overlays
 * stay proportional at any distance from the camera.
 *
 * Blending:
 *  - Lips:   'color' (shade hue/saturation, skin luminance → texture shows through) + light 'multiply' for depth
 *  - Blush:  radial gradient, 'multiply' + 'color' at low alpha, rotated with head roll
 *  - Liner:  tapered filled ribbon along the upper lash line, 'multiply'
 */

import {
  LEFT_CHEEK,
  LEFT_EYE_UPPER,
  LIPS_INNER,
  LIPS_OUTER,
  RIGHT_CHEEK,
  RIGHT_EYE_UPPER,
  dist,
  faceWidth,
  mid,
  roll,
  type Point,
} from './landmarks';

export interface Layer {
  enabled: boolean;
  shadeId: string;
  hex: string;
  /** 0–1 */
  intensity: number;
}

export interface Look {
  lips: Layer;
  blush: Layer;
  liner: Layer & { wing: boolean };
}

/** Closed curve through points using midpoint quadratic smoothing (no polygon corners). */
function smoothClosed(path: Path2D, pts: Point[]) {
  const n = pts.length;
  const start = mid(pts[n - 1], pts[0]);
  path.moveTo(start.x, start.y);
  for (let i = 0; i < n; i++) {
    const next = mid(pts[i], pts[(i + 1) % n]);
    path.quadraticCurveTo(pts[i].x, pts[i].y, next.x, next.y);
  }
  path.closePath();
}

function rgba(hex: string, alpha: number): string {
  const v = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(v >> 16) & 255}, ${(v >> 8) & 255}, ${v & 255}, ${alpha})`;
}

export function drawLips(ctx: CanvasRenderingContext2D, pts: Point[], layer: Layer) {
  const fw = faceWidth(pts);
  const path = new Path2D();
  smoothClosed(path, LIPS_OUTER.map((i) => pts[i]));
  smoothClosed(path, LIPS_INNER.map((i) => pts[i]));

  ctx.save();
  ctx.filter = `blur(${Math.max(0.6, fw * 0.004)}px)`; // feathered edge, like real lipstick
  ctx.fillStyle = layer.hex;
  ctx.globalCompositeOperation = 'multiply';
  ctx.globalAlpha = 0.3 * layer.intensity;
  ctx.fill(path, 'evenodd');
  ctx.globalCompositeOperation = 'color';
  ctx.globalAlpha = 0.75 * layer.intensity;
  ctx.fill(path, 'evenodd');
  ctx.restore();
}

export function drawBlush(ctx: CanvasRenderingContext2D, pts: Point[], layer: Layer) {
  const fw = faceWidth(pts);
  const r = fw * 0.13;
  const angle = roll(pts);

  ctx.save();
  ctx.filter = `blur(${fw * 0.01}px)`;
  for (const idx of [RIGHT_CHEEK, LEFT_CHEEK]) {
    const c = pts[idx];
    for (const [op, alpha] of [
      ['multiply', 0.35],
      ['color', 0.3],
    ] as const) {
      ctx.save();
      ctx.translate(c.x, c.y);
      ctx.rotate(angle);
      ctx.scale(1.25, 0.85); // blush is wider than tall, along the cheekbone
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
      g.addColorStop(0, rgba(layer.hex, 1));
      g.addColorStop(0.55, rgba(layer.hex, 0.55));
      g.addColorStop(1, rgba(layer.hex, 0));
      ctx.globalCompositeOperation = op;
      ctx.globalAlpha = alpha * layer.intensity;
      ctx.fillStyle = g;
      ctx.fillRect(-r, -r, r * 2, r * 2);
      ctx.restore();
    }
  }
  ctx.restore();
}

/** One eye: ribbon from inner to outer corner along the lash line, thicker at the outer end. */
function linerPath(pts: Point[], lid: number[], wing: boolean): Path2D {
  const lash = lid.map((i) => pts[i]).reverse(); // inner → outer
  const inner = lash[0];
  const outer = lash[lash.length - 1];
  const eyeW = dist(inner, outer);
  const axis = { x: (outer.x - inner.x) / eyeW, y: (outer.y - inner.y) / eyeW };
  // Normal pointing towards the brow: the side where the lid's middle sits.
  let n = { x: -axis.y, y: axis.x };
  const lidMid = lash[Math.floor(lash.length / 2)];
  const corners = mid(inner, outer);
  if ((lidMid.x - corners.x) * n.x + (lidMid.y - corners.y) * n.y < 0) n = { x: -n.x, y: -n.y };

  const thick = (t: number) => eyeW * (0.025 + 0.06 * t * t); // taper: fine inside, bolder outside
  const top = lash.map((p, i) => {
    const t = i / (lash.length - 1);
    return { x: p.x + n.x * thick(t), y: p.y + n.y * thick(t) };
  });

  const path = new Path2D();
  path.moveTo(lash[0].x, lash[0].y);
  for (const p of lash.slice(1)) path.lineTo(p.x, p.y);
  if (wing) {
    // Flick: continue along the eye axis and lift towards the brow.
    const tip = { x: outer.x + axis.x * eyeW * 0.28 + n.x * eyeW * 0.16, y: outer.y + axis.y * eyeW * 0.28 + n.y * eyeW * 0.16 };
    path.lineTo(tip.x, tip.y);
  }
  for (const p of top.reverse()) path.lineTo(p.x, p.y);
  path.closePath();
  return path;
}

export function drawLiner(ctx: CanvasRenderingContext2D, pts: Point[], layer: Look['liner']) {
  const fw = faceWidth(pts);
  ctx.save();
  ctx.filter = `blur(${Math.max(0.4, fw * 0.0015)}px)`;
  ctx.fillStyle = layer.hex;
  ctx.globalCompositeOperation = 'multiply';
  ctx.globalAlpha = Math.min(1, 0.45 + 0.55 * layer.intensity);
  for (const lid of [RIGHT_EYE_UPPER, LEFT_EYE_UPPER]) ctx.fill(linerPath(pts, lid, layer.wing));
  ctx.restore();
}

/** Composite the enabled layers onto a canvas that already holds the camera frame. */
export function drawLook(ctx: CanvasRenderingContext2D, pts: Point[], look: Look) {
  if (look.blush.enabled) drawBlush(ctx, pts, look.blush);
  if (look.lips.enabled) drawLips(ctx, pts, look.lips);
  if (look.liner.enabled) drawLiner(ctx, pts, look.liner);
}
