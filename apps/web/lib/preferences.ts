/**
 * Onboarding vocabulary. IDs must match the API enums in apps/api/app/schemas.py.
 */

export type Budget = 'low' | 'mid' | 'high';
export type StylePreference = 'everyday' | 'minimal' | 'classic' | 'bold' | 'formal';
export type Category = 'hair' | 'eyewear' | 'makeup';
export type StyleGoal = 'hair' | 'eyewear' | 'makeup' | 'palette' | 'everyday_refresh' | 'special_occasion';
export type Occasion = 'everyday' | 'work' | 'interviews' | 'festive' | 'evening' | 'dates' | 'travel';

export interface Preferences {
  style_goals: StyleGoal[];
  occasions: Occasion[];
  budget: Budget | null;
  style: StylePreference | null;
  categories: Category[];
}

export interface Option<T extends string> {
  value: T;
  label: string;
  description?: string;
}

export const STYLE_GOALS: Option<StyleGoal>[] = [
  { value: 'hair', label: 'Find haircuts that suit me', description: 'Cuts matched to your face shape' },
  { value: 'eyewear', label: 'Choose flattering eyewear', description: 'Frames that balance your features' },
  { value: 'makeup', label: 'Discover my makeup shades', description: 'Lip and cheek colours for your undertone' },
  { value: 'palette', label: 'Know my colour palette', description: 'Shades to wear near your face' },
  { value: 'everyday_refresh', label: 'Refresh my everyday look', description: 'Small changes, daily confidence' },
  { value: 'special_occasion', label: 'Prepare for an occasion', description: 'A look for a day that matters' },
];

export const OCCASIONS: Option<Occasion>[] = [
  { value: 'everyday', label: 'Everyday & college' },
  { value: 'work', label: 'Work & office' },
  { value: 'interviews', label: 'Interviews' },
  { value: 'festive', label: 'Weddings & festivals' },
  { value: 'evening', label: 'Parties & evenings' },
  { value: 'dates', label: 'Dates' },
  { value: 'travel', label: 'Travel' },
];

export const BUDGETS: Option<Budget>[] = [
  { value: 'low', label: 'Budget-friendly', description: 'Affordable, easy-to-find options' },
  { value: 'mid', label: 'Mid-range', description: 'A balance of price and quality' },
  { value: 'high', label: 'Premium', description: 'Happy to invest in the right pick' },
];

export const STYLES: Option<StylePreference>[] = [
  { value: 'everyday', label: 'Everyday', description: 'Easy, wearable, low effort' },
  { value: 'minimal', label: 'Minimal', description: 'Clean lines, nothing extra' },
  { value: 'classic', label: 'Classic', description: 'Timeless and polished' },
  { value: 'bold', label: 'Bold', description: 'Statement colour and shape' },
  { value: 'formal', label: 'Formal', description: 'Sharp and occasion-ready' },
];

/** Recommendation categories follow from goals; if none match, show all three. */
export function categoriesFor(goals: StyleGoal[]): Category[] {
  const cats = (['hair', 'eyewear', 'makeup'] as const).filter((c) => goals.includes(c));
  return cats.length ? [...cats] : ['hair', 'eyewear', 'makeup'];
}

export const labelOf = <T extends string>(options: Option<T>[], value: T | null | undefined) => options.find((o) => o.value === value)?.label;
