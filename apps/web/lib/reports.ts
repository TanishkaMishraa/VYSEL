export type FaceShape = 'oval' | 'round' | 'square' | 'heart' | 'oblong' | 'diamond';
export type Undertone = 'warm' | 'cool' | 'neutral' | 'olive';
export type SkinDepth = 'fair' | 'light' | 'medium' | 'tan' | 'deep';
export type FeatureContrast = 'low' | 'medium' | 'high';
export type Season = 'spring' | 'summer' | 'autumn' | 'winter';
export type RecommendationCategory = 'hair' | 'eyewear' | 'makeup' | 'outfit_color' | 'outfit_cut';

export interface RecommendationFeatures {
  face_shape: { value: FaceShape; confidence: number };
  undertone: { value: Undertone; confidence: number };
  skin_depth: { value: SkinDepth; confidence: number };
  contrast: { value: FeatureContrast; confidence: number };
}

export interface Recommendation {
  id: string;
  label: string;
  reason: string;
  score: number;
  budget: 'low' | 'mid' | 'high';
  within_budget: boolean | null;
  color_hex: string | null;
}

export interface Recommendations {
  features: RecommendationFeatures;
  season: { value: Season; confidence: number; rationale: string };
  palette: { name: string; hex: string; role: 'base' | 'accent' | 'neutral'; wear: string }[];
  recommendations: { category: RecommendationCategory; items: Recommendation[] }[];
  scoring: { feature_fit: number; style_goal: number; personal_style: number; occasion: number; budget: number };
  disclaimer: string;
}

export interface Report {
  id: string;
  created_at: string;
  report_data: Recommendations;
  share_enabled: boolean;
  feedback: { recommendation_id: string; helpful: boolean; updated_at: string }[];
}

export interface ReportListItem {
  id: string;
  created_at: string;
  season: Season;
  recommendation_count: number;
  share_enabled: boolean;
}
