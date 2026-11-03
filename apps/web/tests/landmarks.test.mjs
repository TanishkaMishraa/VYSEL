import test from 'node:test';
import assert from 'node:assert/strict';
import {
  toPixels,
  dist,
  mid,
  faceWidth,
  roll,
  LandmarkSmoother,
  FACE_EDGE_RIGHT,
  FACE_EDGE_LEFT,
  RIGHT_EYE_OUTER,
  LEFT_EYE_OUTER,
} from '../lib/tryon/landmarks.ts';

test('landmarks - toPixels converts normalized coordinates with and without mirroring', () => {
  const norm = [
    { x: 0.25, y: 0.5 },
    { x: 0.75, y: 0.8 },
  ];
  const width = 640;
  const height = 480;

  const standard = toPixels(norm, width, height, false);
  assert.deepStrictEqual(standard, [
    { x: 160, y: 240 },
    { x: 480, y: 384 },
  ]);

  const mirrored = toPixels(norm, width, height, true);
  assert.deepStrictEqual(mirrored, [
    { x: (1 - 0.25) * 640, y: 240 },
    { x: (1 - 0.75) * 640, y: 384 },
  ]);
});

test('landmarks - distance, midpoint, and faceWidth geometry math', () => {
  const p1 = { x: 0, y: 0 };
  const p2 = { x: 3, y: 4 };

  assert.strictEqual(dist(p1, p2), 5);
  assert.deepStrictEqual(mid(p1, p2), { x: 1.5, y: 2 });

  // Create a 478-length array for faceWidth check
  const pts = Array.from({ length: 478 }, () => ({ x: 0, y: 0 }));
  pts[FACE_EDGE_RIGHT] = { x: 100, y: 200 };
  pts[FACE_EDGE_LEFT] = { x: 250, y: 200 };

  assert.strictEqual(faceWidth(pts), 150);
});

test('landmarks - head roll angle calculation', () => {
  const pts = Array.from({ length: 478 }, () => ({ x: 0, y: 0 }));

  // Perfectly horizontal eyes
  pts[RIGHT_EYE_OUTER] = { x: 100, y: 150 };
  pts[LEFT_EYE_OUTER] = { x: 200, y: 150 };
  assert.strictEqual(roll(pts), 0);

  // Tilted eyes (dy = 10, dx = 100)
  pts[LEFT_EYE_OUTER] = { x: 200, y: 160 };
  const angle = roll(pts);
  assert.ok(Math.abs(angle - Math.atan2(10, 100)) < 1e-6);
});

test('landmarks - LandmarkSmoother reduces jitter on subtle movements', () => {
  const smoother = new LandmarkSmoother(0.5, 0.05, 30);

  const initial = [
    { x: 100, y: 100 },
    { x: 200, y: 200 },
  ];

  // First frame sets baseline
  const f1 = smoother.smooth(initial, 100);
  assert.deepStrictEqual(f1, initial);

  // Small perturbation (jitter) should be smoothed
  const noisy = [
    { x: 101, y: 100 },
    { x: 200, y: 201 },
  ];
  const f2 = smoother.smooth(noisy, 100);

  // x should be between 100 and 101, not jumping immediately to 101
  assert.ok(f2[0].x > 100 && f2[0].x < 101);
  assert.ok(f2[1].y > 200 && f2[1].y < 201);

  // Reset clears state
  smoother.reset();
  const fresh = [
    { x: 300, y: 300 },
    { x: 400, y: 400 },
  ];
  const f3 = smoother.smooth(fresh, 100);
  assert.deepStrictEqual(f3, fresh);
});

