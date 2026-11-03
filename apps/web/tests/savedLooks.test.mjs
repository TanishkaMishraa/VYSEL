import test from 'node:test';
import assert from 'node:assert/strict';
import { serializeLook, restoreLook } from '../lib/tryon/savedLooks.ts';

test('savedLooks - serialize and restore preserve complete look state', () => {
  const originalLook = {
    lips: {
      enabled: true,
      shadeId: 'starter.lips.b85f70',
      shadeName: 'Soft rose',
      hex: '#B85F70',
      intensity: 0.65,
    },
    blush: {
      enabled: true,
      shadeId: 'starter.blush.d98a92',
      shadeName: 'Soft pink',
      hex: '#D98A92',
      intensity: 0.4,
    },
    liner: {
      enabled: true,
      shadeId: 'starter.liner.1a1416',
      shadeName: 'Black',
      hex: '#1A1416',
      intensity: 0.8,
      wing: true,
    },
  };

  const serialized = serializeLook(originalLook);

  // Check snake_case transformation for API payload
  assert.strictEqual(serialized.lips.enabled, true);
  assert.strictEqual(serialized.lips.shade_id, 'starter.lips.b85f70');
  assert.strictEqual(serialized.lips.shade_name, 'Soft rose');
  assert.strictEqual(serialized.lips.hex, '#B85F70');
  assert.strictEqual(serialized.lips.intensity, 0.65);

  assert.strictEqual(serialized.blush.shade_id, 'starter.blush.d98a92');
  assert.strictEqual(serialized.blush.intensity, 0.4);

  assert.strictEqual(serialized.liner.shade_id, 'starter.liner.1a1416');
  assert.strictEqual(serialized.liner.wing, true);

  // Check round-trip restoration
  const restored = restoreLook(serialized);
  assert.deepStrictEqual(restored, originalLook);
});

test('savedLooks - disabled layers serialize correctly', () => {
  const allDisabledLook = {
    lips: { enabled: false, shadeId: 'l1', shadeName: 'Lip1', hex: '#111111', intensity: 0.5 },
    blush: { enabled: false, shadeId: 'b1', shadeName: 'Blush1', hex: '#222222', intensity: 0.5 },
    liner: { enabled: false, shadeId: 'e1', shadeName: 'Liner1', hex: '#333333', intensity: 0.5, wing: false },
  };

  const serialized = serializeLook(allDisabledLook);
  assert.strictEqual(serialized.lips.enabled, false);
  assert.strictEqual(serialized.blush.enabled, false);
  assert.strictEqual(serialized.liner.enabled, false);
  assert.strictEqual(serialized.liner.wing, false);

  const restored = restoreLook(serialized);
  assert.deepStrictEqual(restored, allDisabledLook);
});

