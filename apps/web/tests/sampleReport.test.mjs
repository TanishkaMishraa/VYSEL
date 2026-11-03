import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sampleFeatures,
  samplePalette,
  samplePicks,
  rankPicks,
  WEIGHTS,
} from '../lib/sample-report.ts';

test('sampleReport - sample data structures match Style DNA expectations', () => {
  assert.strictEqual(sampleFeatures.faceShape.value, 'Oval');
  assert.strictEqual(sampleFeatures.undertone.value, 'Neutral');
  assert.strictEqual(sampleFeatures.skinDepth.value, 'Medium');

  assert.strictEqual(samplePalette.length, 5);
  for (const color of samplePalette) {
    assert.ok(/^#[0-9A-Fa-f]{6}$/.test(color.hex));
    assert.ok(['base', 'accent', 'neutral'].includes(color.role));
  }

  assert.ok(samplePicks.hair.length >= 3);
  assert.ok(samplePicks.eyewear.length >= 3);
  assert.ok(samplePicks.makeup.length >= 3);
});

test('sampleReport - rankPicks weights scoring by fit, style, and budget', () => {
  const hairPicks = samplePicks.hair;

  // Rank with minimal style and low budget
  const rankedLow = rankPicks(hairPicks, { budget: 'low', style: 'minimal' });

  // Top result should be sorted descending by score
  for (let i = 0; i < rankedLow.length - 1; i++) {
    assert.ok(rankedLow[i].score >= rankedLow[i + 1].score, 'items should be sorted descending by score');
  }

  // Items matching both style and budget should score higher than without
  const topPick = rankedLow[0];
  assert.ok(topPick.score > 0 && topPick.score <= 1.0);
  assert.strictEqual(
    topPick.score,
    WEIGHTS.fit * topPick.fit +
      WEIGHTS.style * (topPick.matchesStyle ? 1 : 0.4) +
      WEIGHTS.budget * (topPick.withinBudget ? 1 : 0.2),
  );
});

