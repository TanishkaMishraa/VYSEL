#!/usr/bin/env node
/**
 * Builds VYSEL brand assets from a single glyph definition.
 *
 *   node scripts/build-brand-assets.mjs
 *
 * Outputs
 *   packages/ui/assets/brand/*.svg              – static wordmark, monogram, icons
 *   packages/ui/src/brand/brand-paths.json      – path data consumed by <Wordmark/> & <Monogram/>
 *
 * Glyphs are drawn on a 100-unit cap height. Contrast model: thick stems 14u,
 * hairlines 4.5u, no serifs — a high-contrast "glyphic" capital that stays crisp
 * from favicon to billboard. Never re-typeset the wordmark in a font.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const assetsDir = join(root, 'packages/ui/assets/brand');
const srcDir = join(root, 'packages/ui/src/brand');

// Brand colours are duplicated here deliberately: static SVGs cannot read CSS variables.
// Keep in sync with packages/ui/tokens/tokens.css (checked by scripts/validate-design-system.mjs).
const COLOR = {
  obsidian: '#0B0A0C',
  porcelain: '#F7F1EA',
  roseGold300: '#E9C6B3',
  roseGold500: '#C48A73',
  roseGold700: '#8A5743',
};

// ── Glyphs (cap height 100, baseline y=100) ───────────────────────────────
const GLYPHS = {
  // Thick left diagonal, hairline right; inner edges meet at the crotch.
  V: { width: 71, d: 'M0 0 H15 L41.8 81.25 L67 0 H71 L40 100 H33 Z' },
  Y: { width: 70, d: 'M0 0 H15.65 L40.6 49.85 L65.5 0 H70 L42 56 V100 H28 V56 Z' },
  // Thick spine, hairline bowls; overshoots cap height and baseline by 1.5u.
  S: {
    width: 56,
    overshoot: 1.5,
    d:
      'M50.6 10.8 C44.6 2.8 39 0 28 0 C14.5 0 3.5 10.8 3.5 24 C3.5 36 14.7 47.2 23.8 54.95 ' +
      'C31.4 61.4 43.5 66 43.5 76 C43.5 86.5 36.6 95 28 95 C19 95 13.9 90.4 7 86.3 L5 89.7 ' +
      'C13.6 94.8 16 100 28 100 C41.5 100 52.5 89.2 52.5 76 C52.5 63 41.3 52.8 32.2 45.05 ' +
      'C24.6 38.6 12.5 34 12.5 24 C12.5 13.5 19.4 5 28 5 C37 5 43.2 7.6 47.4 13.2 Z',
  },
  E: { width: 48, d: 'M0 0 H47 V4.5 H14 V47.75 H41 V52.25 H14 V95.5 H48 V100 H0 Z' },
  L: { width: 46, d: 'M0 0 H14 V95.5 H46 V100 H0 Z' },
};

// Optical spacing (left offset of each glyph). Diagonal pairs sit tighter.
const LAYOUT = [
  ['V', 0],
  ['Y', 85],
  ['S', 171.5],
  ['E', 246],
  ['L', 314],
];
const WORDMARK_W = 360;
const PAD = 2; // room for S overshoot

// ── Minimal path transformer (absolute M/L/H/V/C/Z only) ──────────────────
function transformPath(d, { dx = 0, dy = 0, sy = 1, cy = 50 } = {}) {
  const tokens = d.match(/[MLHVCZ]|-?\d*\.?\d+/g);
  const out = [];
  let cmd = '';
  let argIdx = 0;
  const fx = (x) => +(x + dx).toFixed(2);
  const fy = (y) => +(cy + (y - cy) * sy + dy).toFixed(2);
  for (const t of tokens) {
    if (/[MLHVCZ]/.test(t)) {
      cmd = t;
      argIdx = 0;
      out.push(t);
      continue;
    }
    const n = parseFloat(t);
    if (cmd === 'H') out.push(fx(n));
    else if (cmd === 'V') out.push(fy(n));
    else out.push(argIdx % 2 === 0 ? fx(n) : fy(n));
    argIdx++;
  }
  return out.join(' ').replace(/ ([MLHVCZ])/g, '$1').replace(/([MLHVCZ]) /g, '$1');
}

const wordmarkPath = LAYOUT.map(([ch, x]) => {
  const g = GLYPHS[ch];
  const sy = g.overshoot ? (100 + 2 * g.overshoot) / 100 : 1;
  return transformPath(g.d, { dx: x, dy: PAD, sy });
}).join('');

// Monogram: the V cradling a faceted gem — "your features, revealed".
const MONO = 120;
const monoV = transformPath(GLYPHS.V.d, { dx: (MONO - 71) / 2, dy: 10 });
// Facet: elongated rhombus in the V's counter, aligned to the crotch axis.
const facetCx = (MONO - 71) / 2 + 41;
const facet = `M${facetCx} 14 L${facetCx + 7} 27 L${facetCx} 40 L${facetCx - 7} 27 Z`;

// Favicon: heavier hairline (8u) so the V survives at 16px.
const favV = 'M0 0 H17 L39.5 72.7 L61 0 H70 L40.5 100 H31 Z';
const favicon = transformPath(favV, { dx: 29, dy: 14 }); // centred in a 128×128 tile

const header = (w, h, title) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="t"><title id="t">${title}</title>`;

const gradient = `<defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${COLOR.roseGold300}"/><stop offset=".55" stop-color="${COLOR.roseGold500}"/><stop offset="1" stop-color="${COLOR.roseGold700}"/></linearGradient></defs>`;

const H = 100 + PAD * 2;
const files = {
  'vysel-wordmark.svg': `${header(WORDMARK_W, H, 'VYSEL')}<path fill="${COLOR.obsidian}" d="${wordmarkPath}"/></svg>`,
  'vysel-wordmark-porcelain.svg': `${header(WORDMARK_W, H, 'VYSEL')}<path fill="${COLOR.porcelain}" d="${wordmarkPath}"/></svg>`,
  'vysel-wordmark-rose-gold.svg': `${header(WORDMARK_W, H, 'VYSEL')}${gradient}<path fill="url(#rg)" d="${wordmarkPath}"/></svg>`,
  'vysel-monogram.svg': `${header(MONO, MONO, 'VYSEL monogram')}${gradient}<path fill="${COLOR.obsidian}" d="${monoV}"/><path fill="url(#rg)" d="${facet}"/></svg>`,
  'vysel-app-icon.svg': `${header(512, 512, 'VYSEL')}${gradient}<rect width="512" height="512" rx="112" fill="${COLOR.obsidian}"/><g transform="translate(64 64) scale(3.2)"><path fill="url(#rg)" d="${monoV}"/><path fill="${COLOR.porcelain}" d="${facet}"/></g></svg>`,
  'favicon.svg': `${header(128, 128, 'VYSEL')}<rect width="128" height="128" rx="28" fill="${COLOR.obsidian}"/><path fill="${COLOR.roseGold500}" d="${favicon}"/></svg>`,
};

mkdirSync(assetsDir, { recursive: true });
mkdirSync(srcDir, { recursive: true });
for (const [name, svg] of Object.entries(files)) writeFileSync(join(assetsDir, name), svg + '\n');

const brandPaths = {
  $comment: 'GENERATED by scripts/build-brand-assets.mjs — do not edit by hand.',
  wordmark: { viewBox: `0 0 ${WORDMARK_W} ${H}`, d: wordmarkPath },
  monogram: { viewBox: `0 0 ${MONO} ${MONO}`, d: monoV, facet },
};
writeFileSync(join(srcDir, 'brand-paths.json'), JSON.stringify(brandPaths, null, 2) + '\n');
// Same data for the no-build showcase (file:// pages cannot fetch JSON).
writeFileSync(
  join(root, 'packages/ui/showcase/brand-paths.js'),
  `// GENERATED by scripts/build-brand-assets.mjs — do not edit by hand.\nwindow.VYSEL_BRAND = ${JSON.stringify(brandPaths)};\n`,
);

console.log(`Wrote ${Object.keys(files).length} SVGs, brand-paths.json and showcase/brand-paths.js`);
