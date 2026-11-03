'use client';

import type { CSSProperties } from 'react';
import { Badge, Button } from '@vysel/ui';
import type { Look } from '@/lib/tryon/render';
import type { LayerKey, Preset, ShadeSet } from '@/lib/tryon/shades';

const LAYERS: { key: LayerKey; label: string; hint: string }[] = [
  { key: 'lips', label: 'Lips', hint: 'Lipstick' },
  { key: 'blush', label: 'Blush', hint: 'Cheeks' },
  { key: 'liner', label: 'Liner', hint: 'Upper lash line' },
];

interface Props {
  shades: ShadeSet;
  look: Look;
  onChange: (look: Look) => void;
  presets: Preset[];
  activePreset: string | null;
  onPreset: (preset: Preset) => void;
  onReset: () => void;
}

export function ShadePicker({ shades, look, onChange, presets, activePreset, onPreset, onReset }: Props) {
  const update = <K extends LayerKey>(key: K, patch: Partial<Look[K]>) => onChange({ ...look, [key]: { ...look[key], ...patch } });

  return (
    <div className="to-picker">
      <section className="to-picker__presets" aria-labelledby="to-presets">
        <div className="to-picker__row">
          <h2 className="vy-overline" id="to-presets">
            Combinations
          </h2>
          <Button variant="link" onClick={onReset}>
            Reset
          </Button>
        </div>
        <div className="to-presets">
          {presets.map((p) => (
            <button key={p.id} type="button" className="to-preset" aria-pressed={activePreset === p.id} onClick={() => onPreset(p)}>
              <span className="to-preset__label">{p.label}</span>
              <span className="to-preset__desc">{p.description}</span>
            </button>
          ))}
        </div>
      </section>

      {LAYERS.map(({ key, label, hint }) => {
        const layer = look[key];
        const list = shades[key];
        const selected = list.find((s) => s.id === layer.shadeId) ??
          list.find((s) => s.hex.toLowerCase() === layer.hex.toLowerCase()) ??
          { id: layer.shadeId, name: layer.shadeName, hex: layer.hex, recommended: false };
        return (
          <fieldset key={key} className="to-layer" data-enabled={layer.enabled}>
            <legend className="vy-visually-hidden">{label}</legend>
            <div className="to-picker__row">
              <label className="to-switch">
                <input type="checkbox" role="switch" checked={layer.enabled} onChange={(e) => update(key, { enabled: e.target.checked })} />
                <span className="to-switch__track" aria-hidden="true" />
                <span>
                  <span className="to-layer__name">{label}</span>
                  <span className="to-layer__hint">{hint}</span>
                </span>
              </label>
              <span className="vy-caption">{selected.name}</span>
            </div>

            {/* Native radios: arrow keys move between shades; screen readers read name + recommendation. */}
            <div className="to-swatches" role="radiogroup" aria-label={`${label} shade`}>
              {list.map((s) => (
                <label key={s.id} className="to-swatch" title={s.reason ? `${s.name} — ${s.reason}` : s.name}>
                  <input
                    type="radio"
                    name={`to-${key}`}
                    value={s.id}
                    checked={layer.shadeId === s.id}
                    onChange={() => update(key, { shadeId: s.id, shadeName: s.name, hex: s.hex, enabled: true })}
                    aria-label={`${s.name}${s.recommended ? ', recommended for you' : ''}`}
                  />
                  <span className="to-swatch__chip" style={{ '--to-c': s.hex } as CSSProperties} aria-hidden="true" />
                  {s.recommended && <span className="to-swatch__dot" aria-hidden="true" />}
                </label>
              ))}
            </div>
            {selected.recommended && selected.reason && <p className="to-layer__reason">{selected.reason}</p>}

            <div className="to-controls">
              <label className="to-range">
                <span className="vy-label">Intensity</span>
                <input
                  type="range"
                  min={10}
                  max={100}
                  step={5}
                  value={Math.round(layer.intensity * 100)}
                  onChange={(e) => update(key, { intensity: Number(e.target.value) / 100, enabled: true })}
                  aria-valuetext={`${Math.round(layer.intensity * 100)} percent`}
                />
                <span className="vy-caption vy-numeric">{Math.round(layer.intensity * 100)}%</span>
              </label>
              {key === 'liner' && (
                <label className="to-check">
                  <input type="checkbox" checked={look.liner.wing} onChange={(e) => update('liner', { wing: e.target.checked, enabled: true })} />
                  <span>Winged</span>
                </label>
              )}
            </div>
          </fieldset>
        );
      })}

      <p className="vy-caption to-picker__legend">
        <span className="to-swatch__dot to-swatch__dot--inline" aria-hidden="true" />
        {shades.source === 'style-dna' ? 'Recommended from your Style DNA' : 'Starter shades — not personalised yet'}
        {shades.source === 'starter' && <Badge tone="estimate">Sample</Badge>}
      </p>
    </div>
  );
}
