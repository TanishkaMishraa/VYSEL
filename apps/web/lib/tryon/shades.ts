/**
 * Shade sets for the try-on. Personalised sets come from the user's latest Style DNA
 * report (makeup.lip.* / makeup.cheek.* recommendations + palette); everyone also gets
 * starter shades to explore, clearly marked as not personalised.
 */

import type { Report } from '@/lib/reports';
import type { Look } from './render';

export type LayerKey = 'lips' | 'blush' | 'liner';

export interface Shade {
  id: string;
  name: string;
  hex: string;
  recommended: boolean;
  reason?: string;
}

export interface ShadeSet {
  source: 'style-dna' | 'starter';
  reportId?: string;
  lips: Shade[];
  blush: Shade[];
  liner: Shade[];
}

const starter = (layer: LayerKey, name: string, hex: string): Shade => ({ id: `starter.${layer}.${hex.slice(1).toLowerCase()}`, name, hex, recommended: false });

export const STARTER_SHADES: ShadeSet = {
  source: 'starter',
  lips: [
    starter('lips', 'Soft rose', '#B85F70'),
    starter('lips', 'Warm coral', '#D76F53'),
    starter('lips', 'Rose mauve', '#A76572'),
    starter('lips', 'Rosewood', '#98604F'),
    starter('lips', 'Classic red', '#A3262E'),
    starter('lips', 'Berry', '#7E2A4A'),
  ],
  blush: [
    starter('blush', 'Soft pink', '#D98A92'),
    starter('blush', 'Muted berry', '#A64F69'),
    starter('blush', 'Soft apricot', '#C77B59'),
    starter('blush', 'Terracotta', '#B75B3F'),
  ],
  liner: [
    starter('liner', 'Black', '#1A1416'),
    starter('liner', 'Espresso', '#3B2620'),
    starter('liner', 'Ink navy', '#202B47'),
    starter('liner', 'Plum', '#4A2340'),
    starter('liner', 'Bronze', '#6B4A2E'),
  ],
};

/** Relative luminance (WCAG) — used to pick liner-suitable deep shades from the palette. */
export function luminance(hex: string): number {
  const v = parseInt(hex.replace('#', ''), 16);
  const [r, g, b] = [(v >> 16) & 255, (v >> 8) & 255, v & 255].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const isHex = (h: string | null | undefined): h is string => !!h && /^#[0-9a-f]{6}$/i.test(h);

/** Personalised shades first, then starter shades not already covered (deduplicated by colour). */
function merge(personal: Shade[], extras: Shade[]): Shade[] {
  const seen = new Set(personal.map((s) => s.hex.toLowerCase()));
  return [...personal, ...extras.filter((s) => !seen.has(s.hex.toLowerCase()))];
}

export function shadesFromReport(report: Report): ShadeSet {
  const makeup = report.report_data.recommendations.find((g) => g.category === 'makeup')?.items ?? [];
  const pick = (prefix: string): Shade[] =>
    makeup
      .filter((i) => i.id.startsWith(prefix) && isHex(i.color_hex))
      .map((i) => ({ id: i.id, name: i.label.replace(/\s+(lip|blush)$/i, ''), hex: i.color_hex!, recommended: true, reason: i.reason }));

  // Liner: the palette's deep shades suit as liner; always keep classic black and espresso.
  const liner = report.report_data.palette
    .filter((c) => isHex(c.hex) && luminance(c.hex) < 0.2) // deep enough to read as liner (e.g. slate, navy, teal)
    .map((c) => ({ id: `palette.${c.name.toLowerCase().replace(/\W+/g, '-')}`, name: c.name, hex: c.hex, recommended: true, reason: `From your ${report.report_data.season.value} palette.` }));

  return {
    source: 'style-dna',
    reportId: report.id,
    lips: merge(pick('makeup.lip.'), STARTER_SHADES.lips),
    blush: merge(pick('makeup.cheek.'), STARTER_SHADES.blush),
    liner: merge(liner, STARTER_SHADES.liner),
  };
}

const layerFrom = (shade: Shade, enabled: boolean, intensity: number) => ({ enabled, shadeId: shade.id, hex: shade.hex, intensity });

/** Starting look (also what Reset returns to): the top lip shade on, everything else off. */
export function initialLook(set: ShadeSet): Look {
  return {
    lips: layerFrom(set.lips[0], true, 0.6),
    blush: layerFrom(set.blush[0], false, 0.5),
    liner: { ...layerFrom(set.liner[0], false, 0.7), wing: false },
  };
}

export interface Preset {
  id: string;
  label: string;
  description: string;
  look: Look;
}

/** Ready-made combinations built from the current shade set (recommended shades first). */
export function presetsFor(set: ShadeSet): Preset[] {
  const deepest = (shades: Shade[]) => [...shades].sort((a, b) => luminance(a.hex) - luminance(b.hex))[0];
  return [
    {
      id: 'natural',
      label: 'Natural',
      description: 'A sheer wash of colour',
      look: { lips: layerFrom(set.lips[0], true, 0.4), blush: layerFrom(set.blush[0], true, 0.3), liner: { ...layerFrom(set.liner[0], false, 0.5), wing: false } },
    },
    {
      id: 'everyday',
      label: 'Everyday',
      description: 'Defined, still easy',
      look: { lips: layerFrom(set.lips[0], true, 0.65), blush: layerFrom(set.blush[0], true, 0.45), liner: { ...layerFrom(set.liner[0], true, 0.55), wing: false } },
    },
    {
      id: 'evening',
      label: 'Evening',
      description: 'Deeper lip, winged liner',
      look: {
        lips: layerFrom(deepest(set.lips), true, 0.85),
        blush: layerFrom(set.blush[set.blush.length > 1 ? 1 : 0], true, 0.5),
        liner: { ...layerFrom(deepest(set.liner), true, 0.9), wing: true },
      },
    },
  ];
}
