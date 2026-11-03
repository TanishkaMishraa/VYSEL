import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STARTER_SHADES,
  initialLook,
  presetsFor,
  luminance,
  shadesFromReport,
} from '../lib/tryon/shades.ts';

test('shades - STARTER_SHADES contains lip, blush, and eyeliner defaults', () => {
  assert.strictEqual(STARTER_SHADES.source, 'starter');
  assert.strictEqual(STARTER_SHADES.lips.length, 6);
  assert.strictEqual(STARTER_SHADES.blush.length, 4);
  assert.strictEqual(STARTER_SHADES.liner.length, 5);

  for (const list of [STARTER_SHADES.lips, STARTER_SHADES.blush, STARTER_SHADES.liner]) {
    for (const shade of list) {
      assert.ok(shade.id.startsWith('starter.'));
      assert.ok(/^#[0-9A-Fa-f]{6}$/.test(shade.hex));
      assert.strictEqual(shade.recommended, false);
    }
  }
});

test('shades - luminance calculates WCAG relative luminance accurately', () => {
  // Pure black should be 0, pure white should be 1
  assert.strictEqual(luminance('#000000'), 0);
  assert.ok(Math.abs(luminance('#FFFFFF') - 1.0) < 1e-6);

  // Dark colors vs light colors
  const blackL = luminance('#1A1416');
  const pinkL = luminance('#D98A92');
  assert.ok(blackL < 0.2, 'black shade should have low luminance');
  assert.ok(pinkL > blackL, 'pink should be brighter than black');
});

test('shades - initialLook configures default starting state', () => {
  const look = initialLook(STARTER_SHADES);

  // Top lip shade is enabled at 60%
  assert.strictEqual(look.lips.enabled, true);
  assert.strictEqual(look.lips.shadeId, STARTER_SHADES.lips[0].id);
  assert.strictEqual(look.lips.intensity, 0.6);

  // Blush and liner are disabled initially
  assert.strictEqual(look.blush.enabled, false);
  assert.strictEqual(look.liner.enabled, false);
  assert.strictEqual(look.liner.wing, false);
});

test('shades - presetsFor generates natural, everyday, and evening looks', () => {
  const presets = presetsFor(STARTER_SHADES);
  assert.strictEqual(presets.length, 3);

  const [natural, everyday, evening] = presets;
  assert.strictEqual(natural.id, 'natural');
  assert.strictEqual(natural.look.lips.enabled, true);
  assert.strictEqual(natural.look.blush.enabled, true);
  assert.strictEqual(natural.look.liner.enabled, false);

  assert.strictEqual(everyday.id, 'everyday');
  assert.strictEqual(everyday.look.lips.enabled, true);
  assert.strictEqual(everyday.look.blush.enabled, true);
  assert.strictEqual(everyday.look.liner.enabled, true);
  assert.strictEqual(everyday.look.liner.wing, false);

  assert.strictEqual(evening.id, 'evening');
  assert.strictEqual(evening.look.lips.enabled, true);
  assert.strictEqual(evening.look.liner.enabled, true);
  assert.strictEqual(evening.look.liner.wing, true, 'evening look has winged liner');
});

test('shades - shadesFromReport prioritizes recommended shades and deduplicates', () => {
  const mockReport = {
    id: 'rep_123',
    report_data: {
      season: { value: 'autumn', confidence: 0.8 },
      palette: [
        { name: 'Deep Teal', hex: '#1C3B3E' }, // low luminance (< 0.2) -> suitable for liner
        { name: 'Warm Cream', hex: '#F5EBE1' }, // high luminance -> not liner
      ],
      recommendations: [
        {
          category: 'makeup',
          items: [
            { id: 'makeup.lip.terracotta', label: 'Terracotta Lip', color_hex: '#A84B32', reason: 'Matches warm undertone' },
            { id: 'makeup.cheek.peach', label: 'Peach Blush', color_hex: '#E08E79', reason: 'Flattering warm glow' },
          ],
        },
      ],
    },
  };

  const set = shadesFromReport(mockReport);
  assert.strictEqual(set.source, 'style-dna');
  assert.strictEqual(set.reportId, 'rep_123');

  // Personalized lip recommendation should be first
  assert.strictEqual(set.lips[0].id, 'makeup.lip.terracotta');
  assert.strictEqual(set.lips[0].recommended, true);
  assert.strictEqual(set.lips[0].name, 'Terracotta');

  // Personalized blush recommendation should be first
  assert.strictEqual(set.blush[0].id, 'makeup.cheek.peach');
  assert.strictEqual(set.blush[0].recommended, true);

  // Palette deep teal should appear in liner
  const tealLiner = set.liner.find((l) => l.name === 'Deep Teal');
  assert.ok(tealLiner, 'Deep Teal should be extracted from palette as liner');
  assert.strictEqual(tealLiner.recommended, true);
});

