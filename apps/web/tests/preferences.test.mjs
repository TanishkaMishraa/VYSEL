import test from 'node:test';
import assert from 'node:assert/strict';
import {
  BUDGETS,
  OCCASIONS,
  STYLE_GOALS,
  STYLES,
  categoriesFor,
  labelOf,
} from '../lib/preferences.ts';

test('preferences - choice catalogues are non-empty and well-structured', () => {
  assert.ok(STYLE_GOALS.length === 6, 'should have 6 style goals');
  assert.ok(OCCASIONS.length === 7, 'should have 7 occasions');
  assert.ok(BUDGETS.length === 3, 'should have 3 budget tiers');
  assert.ok(STYLES.length === 5, 'should have 5 style options');

  for (const list of [STYLE_GOALS, OCCASIONS, BUDGETS, STYLES]) {
    for (const opt of list) {
      assert.ok(typeof opt.value === 'string' && opt.value.length > 0);
      assert.ok(typeof opt.label === 'string' && opt.label.length > 0);
      if (opt.description !== undefined) {
        assert.ok(typeof opt.description === 'string' && opt.description.length > 0);
      }
    }
  }
});

test('preferences - categoriesFor maps goals to categories with all-three fallback', () => {
  // If no category-specific goals selected, default to all three categories
  assert.deepStrictEqual(categoriesFor([]), ['hair', 'eyewear', 'makeup']);
  assert.deepStrictEqual(categoriesFor(['palette', 'everyday_refresh']), ['hair', 'eyewear', 'makeup']);

  // Specific goals filter down to selected categories
  assert.deepStrictEqual(categoriesFor(['hair']), ['hair']);
  assert.deepStrictEqual(categoriesFor(['eyewear']), ['eyewear']);
  assert.deepStrictEqual(categoriesFor(['makeup']), ['makeup']);
  assert.deepStrictEqual(categoriesFor(['hair', 'makeup']), ['hair', 'makeup']);
  assert.deepStrictEqual(categoriesFor(['hair', 'eyewear', 'makeup']), ['hair', 'eyewear', 'makeup']);
});

test('preferences - labelOf finds matching labels or returns undefined', () => {
  assert.strictEqual(labelOf(BUDGETS, 'low'), 'Budget-friendly');
  assert.strictEqual(labelOf(BUDGETS, 'mid'), 'Mid-range');
  assert.strictEqual(labelOf(BUDGETS, 'high'), 'Premium');
  assert.strictEqual(labelOf(BUDGETS, 'unknown_tier'), undefined);

  assert.strictEqual(labelOf(STYLES, 'minimal'), 'Minimal');
  assert.strictEqual(labelOf(OCCASIONS, 'festive'), 'Weddings & festivals');
});
