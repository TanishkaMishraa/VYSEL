/**
 * ILLUSTRATIVE SAMPLE — not a real person's result and not produced by the model.
 * Shapes mirror the API's StyleDNA schema (docs/api/openapi.yaml) so the landing
 * demo and the real report share vocabulary.
 */

export type Budget = 'low' | 'mid' | 'high';
export type Style = 'everyday' | 'minimal' | 'bold';
export type Category = 'hair' | 'eyewear' | 'makeup';

export interface SamplePick {
  id: string;
  label: string;
  /** Fit to the sample's estimated features (0–1). */
  fit: number;
  budget: Budget;
  styles: Style[];
  reason: string;
}

export interface PaletteColor {
  name: string;
  hex: string;
  role: 'base' | 'accent' | 'neutral';
  wear: string;
}

export const sampleFeatures = {
  faceShape: { value: 'Oval', confidence: 0.72, alternative: { value: 'Oblong', confidence: 0.18 } },
  undertone: { value: 'Neutral', confidence: 0.64 },
  skinDepth: { value: 'Medium', confidence: 0.81 },
} as const;

export const sampleTraits = [
  { name: 'Balanced proportions', detail: 'Face length and cheekbone width sit in a gentle ratio, so most cuts and frames work.' },
  { name: 'Soft contrast', detail: 'Low contrast between features favours blended tones over stark black-and-white.' },
  { name: 'Muted warmth', detail: 'A neutral undertone carries both warm and cool shades when they are softened.' },
] as const;

export const samplePalette: PaletteColor[] = [
  { name: 'Rose', hex: '#C27C88', role: 'accent', wear: 'Lips, blush, scarves' },
  { name: 'Sage', hex: '#9CAF88', role: 'base', wear: 'Knitwear and everyday tops' },
  { name: 'Navy', hex: '#1F2A44', role: 'neutral', wear: 'Tailoring, denim, frames' },
  { name: 'Plum', hex: '#6E3B5C', role: 'accent', wear: 'Evening looks and statement lips' },
  { name: 'Cream', hex: '#F3E9D2', role: 'neutral', wear: 'Shirts and near-face neutrals' },
];

export const samplePicks: Record<Category, SamplePick[]> = {
  hair: [
    { id: 'hair.soft_layers', label: 'Soft layers', fit: 0.92, budget: 'mid', styles: ['everyday'], reason: 'Balanced proportions carry layered volume without widening the face.' },
    { id: 'hair.long_waves', label: 'Long waves', fit: 0.88, budget: 'mid', styles: ['everyday', 'bold'], reason: 'Vertical movement complements an oval outline.' },
    { id: 'hair.textured_lob', label: 'Textured lob', fit: 0.84, budget: 'low', styles: ['minimal', 'everyday'], reason: 'Jaw-length texture frames the cheekbones and needs little upkeep.' },
    { id: 'hair.curtain_bangs', label: 'Curtain bangs', fit: 0.8, budget: 'low', styles: ['bold'], reason: 'A centre part with face-framing bangs softens the forehead line.' },
    { id: 'hair.sleek_straight', label: 'Sleek straight', fit: 0.78, budget: 'low', styles: ['minimal'], reason: 'Clean lines suit even proportions without adding width.' },
    { id: 'hair.volume_blowout', label: 'Volume blowout', fit: 0.74, budget: 'high', styles: ['bold'], reason: 'Crown volume adds drama while staying in proportion.' },
  ],
  eyewear: [
    { id: 'eyewear.slim_rectangle', label: 'Slim rectangle', fit: 0.9, budget: 'mid', styles: ['minimal', 'everyday'], reason: 'Gentle angles add definition to soft, balanced features.' },
    { id: 'eyewear.soft_round', label: 'Soft round', fit: 0.84, budget: 'low', styles: ['everyday'], reason: 'Matches the face’s natural curves for an easy everyday look.' },
    { id: 'eyewear.cat_eye', label: 'Cat-eye', fit: 0.8, budget: 'mid', styles: ['bold'], reason: 'An upswept brow line lifts the cheekbones.' },
    { id: 'eyewear.clear_square', label: 'Clear acetate square', fit: 0.77, budget: 'low', styles: ['minimal'], reason: 'Transparent frames keep structure light against soft contrast.' },
    { id: 'eyewear.titanium_rimless', label: 'Titanium rimless', fit: 0.74, budget: 'high', styles: ['minimal'], reason: 'Near-invisible frames let balanced features lead.' },
  ],
  makeup: [
    { id: 'makeup.lip.rose', label: 'Rose lip', fit: 0.92, budget: 'low', styles: ['everyday', 'minimal'], reason: 'Muted pink sits well on a neutral undertone.' },
    { id: 'makeup.lip.berry', label: 'Berry lip', fit: 0.86, budget: 'mid', styles: ['bold'], reason: 'A deeper accent from your palette for evenings.' },
    { id: 'makeup.cheek.peach', label: 'Peach blush', fit: 0.84, budget: 'low', styles: ['everyday'], reason: 'Light, warm-leaning colour that stays soft.' },
    { id: 'makeup.lip.mauve', label: 'Mauve nude', fit: 0.82, budget: 'low', styles: ['minimal'], reason: 'A low-contrast nude that matches soft features.' },
    { id: 'makeup.lip.plum', label: 'Plum evening lip', fit: 0.78, budget: 'mid', styles: ['bold'], reason: 'Echoes the plum accent for a statement look.' },
    { id: 'makeup.base.satin', label: 'Satin-finish base', fit: 0.76, budget: 'high', styles: ['everyday'], reason: 'A satin finish keeps medium depth luminous, not shiny.' },
  ],
};

/**
 * Transparent rule — the same idea as the MVP recommender (deck: "rules score each
 * option on fit, preference and budget"). Weights are illustrative.
 */
export const WEIGHTS = { fit: 0.6, style: 0.25, budget: 0.15 } as const;
const BUDGET_RANK: Record<Budget, number> = { low: 0, mid: 1, high: 2 };

export interface RankedPick extends SamplePick {
  score: number;
  matchesStyle: boolean;
  withinBudget: boolean;
}

export function rankPicks(picks: SamplePick[], prefs: { budget: Budget; style: Style }): RankedPick[] {
  return picks
    .map((p) => {
      const matchesStyle = p.styles.includes(prefs.style);
      const withinBudget = BUDGET_RANK[p.budget] <= BUDGET_RANK[prefs.budget];
      const score = WEIGHTS.fit * p.fit + WEIGHTS.style * (matchesStyle ? 1 : 0.4) + WEIGHTS.budget * (withinBudget ? 1 : 0.2);
      return { ...p, score, matchesStyle, withinBudget };
    })
    .sort((a, b) => b.score - a.score);
}
