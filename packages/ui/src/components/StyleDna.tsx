import type { CSSProperties } from 'react';

/** Palette colour chip. `hex` comes from the API's StyleDNA.palette (data, not a design token). */
export function Swatch({ name, hex }: { name: string; hex: string }) {
  return (
    <span className="vy-swatch">
      <span className="vy-swatch__chip" style={{ '--vy-swatch-color': hex } as CSSProperties} aria-hidden="true" />
      <span>{name}</span>
    </span>
  );
}

/** Confidence meter (0–1) for estimates. Always paired with an estimate badge. */
export function Confidence({ value, label = 'Confidence' }: { value: number; label?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="vy-confidence">
      <span>{label}</span>
      <span
        className="vy-confidence__track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct}%${pct < 50 ? ', low confidence' : ''}`}
      >
        <span className="vy-confidence__fill" style={{ '--vy-value': value } as CSSProperties} />
      </span>
      <span className="vy-numeric">{pct}%</span>
    </div>
  );
}
