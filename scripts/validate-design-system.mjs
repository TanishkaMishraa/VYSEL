#!/usr/bin/env node
/**
 * Design-system consistency & accessibility checks. Zero dependencies.
 *
 *   node scripts/validate-design-system.mjs
 *
 * 1. Every var(--vy-*) used in CSS/JS/TSX is defined in tokens.css (or is a documented runtime var).
 * 2. components.css contains no raw colour literals.
 * 3. Brand colours in build-brand-assets.mjs match token primitives.
 * 4. WCAG 2.x contrast of semantic pairs passes in both themes.
 * 5. Icon paths in showcase/shared.js match Icon.tsx.
 * 6. Every static .vy-* class referenced by React components exists in components.css.
 * 7. Generated brand data is in sync with the SVG assets.
 * 8. Reduced-motion handling exists in tokens and components.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const ui = join(root, 'packages/ui');
const read = (p) => readFileSync(join(ui, p), 'utf8');

const tokens = read('tokens/tokens.css');
const components = read('styles/components.css');
const showcaseCss = read('showcase/showcase.css');
const showcaseJs = read('showcase/showcase.js');
const sharedJs = read('showcase/shared.js');
const showcaseHtml = read('showcase/index.html');
const preset = read('tailwind-preset.cjs');
const tsxFiles = ['src/brand/Wordmark.tsx', ...readdirSync(join(ui, 'src/components')).map((f) => `src/components/${f}`)];
const tsx = Object.fromEntries(tsxFiles.map((f) => [f, read(f)]));

const failures = [];
const ok = (msg) => console.log(`  ✓ ${msg}`);
const fail = (msg) => failures.push(msg);

// ── 1. Token references resolve ─────────────────────────────────────────
const defined = new Set([...tokens.matchAll(/(--vy-[\w-]+)\s*:/g)].map((m) => m[1]));
// Runtime vars set inline by components with data (not design decisions).
const RUNTIME = new Set(['--vy-value', '--vy-swatch-color']);
const presetRefs = [...preset.matchAll(/--vy-\$\{?/g)].length; // templated in preset, checked below
const sources = { 'components.css': components, 'showcase.css': showcaseCss, 'showcase.js': showcaseJs, 'index.html': showcaseHtml, ...tsx };
let refCount = 0;
for (const [name, src] of Object.entries(sources)) {
  for (const m of src.matchAll(/var\((--vy-[\w-]+)\)/g)) {
    refCount++;
    if (!defined.has(m[1]) && !RUNTIME.has(m[1])) fail(`${name}: undefined token ${m[1]}`);
  }
}
// Tailwind preset builds names from arrays; verify each semantic/palette name.
const presetNames = [
  ...[...preset.matchAll(/'([a-z-]+)'/g)].map((m) => m[1]).filter((n) => defined.has(`--vy-${n}`) || /^(bg|surface|text|border|accent|focus|success|warning|danger|info|estimate)/.test(n)),
];
for (const n of presetNames) if (!defined.has(`--vy-${n}`) && !['sans', 'display', 'editorial'].includes(n)) fail(`tailwind-preset: no token --vy-${n}`);
for (const m of preset.matchAll(/var\((--vy-[\w-]+)\)/g)) if (!defined.has(m[1])) fail(`tailwind-preset: undefined token ${m[1]}`);
for (const m of preset.matchAll(/scale\('([\w-]+)', \[([\d, ]+)\]\)/g))
  for (const step of m[2].split(',').map((s) => s.trim())) if (!defined.has(`--vy-${m[1]}-${step}`)) fail(`tailwind-preset: no token --vy-${m[1]}-${step}`);
if (!failures.length) ok(`${refCount} token references resolve (+ Tailwind preset, ${presetRefs ? 'templated' : 'static'} names)`);

// ── 2. No raw colours in components ─────────────────────────────────────
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '');
const comp = stripComments(components);
const rawHex = [...comp.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((m) => m[0]).filter((h) => h !== '#000'); // #000 only inside mask-image
const rawFns = [...comp.matchAll(/rgba?\((?!var\()[^)]*\)/g)].map((m) => m[0]);
const named = [...comp.matchAll(/:\s*(white|black|red|blue|green|gray|grey)\b/g)].map((m) => m[1]);
const masks = [...comp.matchAll(/#000/g)].length;
const maskOk = [...comp.matchAll(/linear-gradient\(#000 0 0\)/g)].length;
if (rawHex.length || rawFns.length || named.length || masks !== maskOk) fail(`components.css raw colours: ${[...rawHex, ...rawFns, ...named].join(', ') || 'stray #000'}`);
else ok('components.css uses tokens only (no raw colours)');

// ── 3. Brand asset colours match tokens ─────────────────────────────────
const build = readFileSync(join(root, 'scripts/build-brand-assets.mjs'), 'utf8');
const hexOf = (token) => {
  const m = tokens.match(new RegExp(`${token}:\\s*(\\d+) (\\d+) (\\d+)`));
  return m && '#' + m.slice(1).map((n) => (+n).toString(16).padStart(2, '0')).join('').toUpperCase();
};
const BRAND_MAP = { obsidian: '--vy-obsidian-950', porcelain: '--vy-porcelain-100', roseGold300: '--vy-rose-gold-300', roseGold500: '--vy-rose-gold-500', roseGold700: '--vy-rose-gold-700' };
let brandOk = true;
for (const [k, token] of Object.entries(BRAND_MAP)) {
  const m = build.match(new RegExp(`${k}: '(#[0-9A-F]{6})'`));
  if (!m || m[1] !== hexOf(token)) { brandOk = false; fail(`build-brand-assets ${k}=${m?.[1]} ≠ ${token} ${hexOf(token)}`); }
}
if (brandOk) ok('brand SVG colours match token primitives');

// ── 4. Contrast (resolve semantic tokens per theme) ─────────────────────
const block = (selector) => {
  const i = tokens.indexOf(selector);
  return tokens.slice(tokens.indexOf('{', i) + 1, tokens.indexOf('\n}', i));
};
const primitives = block(':root {');
const themes = { Obsidian: block(":root,\n[data-theme='obsidian']"), Porcelain: block("[data-theme='porcelain']") };
const resolver = (theme) => {
  const map = new Map();
  for (const src of [primitives, theme]) for (const m of src.matchAll(/(--vy-[\w-]+):\s*([^;]+);/g)) map.set(m[1], m[2].trim());
  const resolve = (name, depth = 0) => {
    const v = map.get(name);
    if (!v || depth > 5) return null;
    const ref = v.match(/^var\((--vy-[\w-]+)\)$/);
    if (ref) return resolve(ref[1], depth + 1);
    const ch = v.match(/^(\d+) (\d+) (\d+)/);
    return ch ? ch.slice(1).map(Number) : null;
  };
  return resolve;
};
const lum = (rgb) => {
  const [r, g, b] = rgb.map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
// Same pairs as the showcase table (showcase.js PAIRS).
const PAIRS = [...showcaseJs.matchAll(/\['([\w-]+)', '([\w-]+)', ([\d.]+), '[^']*'\]/g)].map((m) => [m[1], m[2], +m[3]]);
if (PAIRS.length < 10) fail('could not read contrast pairs from showcase.js');
for (const [themeName, theme] of Object.entries(themes)) {
  const resolve = resolver(theme);
  const bad = [];
  for (const [fg, bg, min] of PAIRS) {
    const a = resolve(`--vy-${fg}`), b = resolve(`--vy-${bg}`);
    if (!a || !b) { bad.push(`${fg}/${bg} unresolved`); continue; }
    const r = ratio(a, b);
    if (r < min) bad.push(`${fg} on ${bg} = ${r.toFixed(2)} < ${min}`);
  }
  if (bad.length) bad.forEach((b) => fail(`${themeName} contrast: ${b}`));
  else ok(`${themeName}: ${PAIRS.length} contrast pairs meet WCAG AA`);
}

// ── 5. Icon parity ──────────────────────────────────────────────────────
const icons = (src) => Object.fromEntries([...src.matchAll(/^\s*(\w+): '([^']+)',$/gm)].map((m) => [m[1], m[2]]));
const a = icons(tsx['src/components/Icon.tsx']), b = icons(sharedJs);
const iconDiff = [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((k) => a[k] !== b[k]);
if (iconDiff.length || !Object.keys(a).length) fail(`icon paths differ between Icon.tsx and shared.js: ${iconDiff.join(', ')}`);
else ok(`${Object.keys(a).length} icons in sync (React ↔ showcase)`);

// ── 6. React → CSS class contract ───────────────────────────────────────
const cssClasses = new Set([...components.matchAll(/\.(vy-[\w-]+)/g)].map((m) => m[1]));
const missing = [];
for (const [f, src] of Object.entries(tsx))
  for (const m of src.matchAll(/['"` ](vy-[a-z][\w-]*[a-z])(?=['"` ])/g)) if (!cssClasses.has(m[1])) missing.push(`${f}: .${m[1]}`);
// Template classes like `vy-btn--${variant}`: check every declared variant.
const VARIANTS = { 'vy-btn--': ['primary', 'secondary', 'ghost', 'link', 'sm', 'lg'], 'vy-card--': ['raised', 'gilded'], 'vy-badge--': ['accent', 'success', 'warning', 'danger', 'info', 'estimate'], 'vy-state--': ['empty', 'success', 'error', 'info'], 'vy-alert--': ['success', 'warning', 'danger'], 'vy-tabs--': ['vertical'] };
for (const [prefix, vs] of Object.entries(VARIANTS)) for (const v of vs) if (!cssClasses.has(prefix + v)) missing.push(`.${prefix}${v}`);
if (missing.length) fail(`classes used but not styled: ${missing.join(', ')}`);
else ok('every class used by React components is styled');

// ── 7. Generated brand data in sync ─────────────────────────────────────
const paths = JSON.parse(read('src/brand/brand-paths.json'));
const svg = read('assets/brand/vysel-wordmark.svg');
if (!svg.includes(paths.wordmark.d) || !read('showcase/brand-paths.js').includes(paths.wordmark.d)) fail('brand assets out of sync — run: node scripts/build-brand-assets.mjs');
else ok('brand-paths.json, showcase data and SVGs in sync');

// ── 8. Reduced motion ───────────────────────────────────────────────────
if (!/prefers-reduced-motion: reduce/.test(tokens) || !/prefers-reduced-motion: reduce/.test(components)) fail('reduced-motion handling missing');
else ok('prefers-reduced-motion handled in tokens and components');

if (failures.length) {
  console.error(`\n✗ ${failures.length} problem(s):`);
  failures.forEach((f) => console.error(`  - ${f}`));
  process.exit(1);
}
console.log('\nDesign system checks passed.');
