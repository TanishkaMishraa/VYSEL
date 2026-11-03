import type { Look } from './render';

export type SavedLookOccasion = 'college' | 'office' | 'party' | 'wedding';

export interface SavedLookData {
  lips: { enabled: boolean; shade_id: string; shade_name: string; hex: string; intensity: number };
  blush: { enabled: boolean; shade_id: string; shade_name: string; hex: string; intensity: number };
  liner: { enabled: boolean; shade_id: string; shade_name: string; hex: string; intensity: number; wing: boolean };
}

export interface SavedTryOnLook {
  id: string;
  name: string;
  occasion: SavedLookOccasion;
  look: SavedLookData;
  created_at: string;
  updated_at: string;
}

export function serializeLook(look: Look): SavedLookData {
  const layer = (value: Look['lips']) => ({
    enabled: value.enabled,
    shade_id: value.shadeId,
    shade_name: value.shadeName,
    hex: value.hex,
    intensity: value.intensity,
  });
  return {
    lips: layer(look.lips),
    blush: layer(look.blush),
    liner: { ...layer(look.liner), wing: look.liner.wing },
  };
}

export function restoreLook(saved: SavedLookData): Look {
  const layer = (value: SavedLookData['lips']) => ({
    enabled: value.enabled,
    shadeId: value.shade_id,
    shadeName: value.shade_name,
    hex: value.hex,
    intensity: value.intensity,
  });
  return {
    lips: layer(saved.lips),
    blush: layer(saved.blush),
    liner: { ...layer(saved.liner), wing: saved.liner.wing },
  };
}
