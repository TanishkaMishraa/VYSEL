'use client';

import { useMemo, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { Alert, Badge, ChoiceChips, Confidence, EstimateBadge, Tabs, type TabItem } from '@vysel/ui';
import {
  rankPicks,
  sampleFeatures,
  samplePalette,
  samplePicks,
  sampleTraits,
  type Budget,
  type Category,
  type Style,
} from '@/lib/sample-report';

const BUDGETS = [
  { value: 'low', label: 'Low' },
  { value: 'mid', label: 'Mid' },
  { value: 'high', label: 'High' },
];
const STYLES = [
  { value: 'everyday', label: 'Everyday' },
  { value: 'minimal', label: 'Minimal' },
  { value: 'bold', label: 'Bold' },
];
const CATEGORY_LABEL: Record<Category, string> = { hair: 'Hair', eyewear: 'Eyewear', makeup: 'Makeup' };

/** Palette as a radio group of swatches: arrow keys move, selection shows how to wear it. */
function PaletteExplorer() {
  const [selected, setSelected] = useState(0);
  const color = samplePalette[selected];

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = (selected + step + samplePalette.length) % samplePalette.length;
    setSelected(next);
    e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
  };

  return (
    <div className="lp-palette">
      <div className="flex items-center justify-between gap-3">
        <h4 className="vy-overline" id="palette-label">
          Colour palette
        </h4>
        <span className="vy-caption">Select a shade</span>
      </div>
      <div className="lp-palette__swatches" role="radiogroup" aria-labelledby="palette-label" onKeyDown={onKeyDown}>
        {samplePalette.map((c, i) => (
          <button
            key={c.name}
            type="button"
            role="radio"
            aria-checked={i === selected}
            aria-label={`${c.name}, ${c.role}`}
            tabIndex={i === selected ? 0 : -1}
            className="lp-swatch-btn"
            onClick={() => setSelected(i)}
          >
            <span style={{ '--lp-c': c.hex } as CSSProperties} />
          </button>
        ))}
      </div>
      <div className="lp-palette__detail" aria-live="polite">
        <span className="lp-palette__chip" style={{ '--lp-c': color.hex } as CSSProperties} aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="lp-feature__value">{color.name}</span>
            <code className="vy-caption">{color.hex}</code>
            <Badge>{color.role}</Badge>
          </div>
          <p className="vy-caption">Wear it: {color.wear}</p>
        </div>
      </div>
    </div>
  );
}

export function StyleDnaReport() {
  const [budget, setBudget] = useState<Budget>('mid');
  const [style, setStyle] = useState<Style>('everyday');
  const prefsLabel = `${STYLES.find((s) => s.value === style)?.label} · ${BUDGETS.find((b) => b.value === budget)?.label} budget`;

  const ranked = useMemo(
    () => (Object.keys(samplePicks) as Category[]).map((cat) => ({ cat, picks: rankPicks(samplePicks[cat], { budget, style }).slice(0, 3) })),
    [budget, style],
  );

  const tabs: TabItem[] = ranked.map(({ cat, picks }) => ({
    id: cat,
    label: CATEGORY_LABEL[cat],
    content: (
      // Keyed by preferences so re-ranked lists animate in afresh.
      <ol className="lp-picks" key={`${cat}-${budget}-${style}`} aria-label={`Top ${CATEGORY_LABEL[cat].toLowerCase()} picks for ${prefsLabel}`}>
        {picks.map((p, i) => (
          <li className="lp-pick" key={p.id} style={{ '--i': i } as CSSProperties}>
            <span className="lp-pick__rank" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <div className="lp-pick__head">
                <span className="lp-pick__label">{p.label}</span>
                <span className="vy-caption vy-numeric">Score {p.score.toFixed(2)}</span>
              </div>
              <p className="vy-caption mt-1">
                {p.reason}
              </p>
              <div className="lp-pick__tags">
                {p.matchesStyle && <Badge tone="accent">Matches {STYLES.find((s) => s.value === style)?.label}</Badge>}
                <Badge tone={p.withinBudget ? 'success' : 'warning'}>{p.withinBudget ? 'Within budget' : 'Above budget'}</Badge>
              </div>
            </div>
          </li>
        ))}
      </ol>
    ),
  }));

  return (
    <article className="vy-card vy-card--gilded lp-report" aria-labelledby="report-title">
      <div className="lp-report__top">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="vy-overline">Sample Style DNA</p>
            <Badge tone="warning">Illustrative · not a real result</Badge>
          </div>
          <h3 className="vy-h3" id="report-title">
            Soft, balanced, <span className="vy-emphasis">quietly warm</span>
          </h3>
        </div>
        <div className="lp-report__controls" aria-label="Try different preferences">
          <ChoiceChips legend="Budget" name="sample-budget" options={BUDGETS} value={budget} onChange={(v) => setBudget(v as Budget)} />
          <ChoiceChips legend="Style" name="sample-style" options={STYLES} value={style} onChange={(v) => setStyle(v as Style)} />
        </div>
      </div>

      <div className="lp-report__grid">
        <div>
          {[
            ['Face shape', sampleFeatures.faceShape],
            ['Undertone', sampleFeatures.undertone],
            ['Skin depth', sampleFeatures.skinDepth],
          ].map(([label, f]) => {
            const feat = f as { value: string; confidence: number };
            return (
              <div className="lp-feature" key={label as string}>
                <div className="lp-feature__head">
                  <span className="vy-overline">{label as string}</span>
                  <EstimateBadge />
                </div>
                <span className="lp-feature__value">{feat.value}</span>
                <Confidence value={feat.confidence} label={`${label} confidence`} />
              </div>
            );
          })}
          <h4 className="vy-overline mt-8">
            Style traits
          </h4>
          <ul className="lp-traits">
            {sampleTraits.map((t) => (
              <li key={t.name}>
                <strong>{t.name}</strong>
                <span className="vy-caption">{t.detail}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col gap-10">
          <PaletteExplorer />
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h4 className="vy-overline">Top picks</h4>
              <span className="vy-caption" aria-live="polite">
                Ranked for {prefsLabel}
              </span>
            </div>
            <Tabs items={tabs} label="Recommendation categories" />
          </div>
        </div>
      </div>

      <div className="lp-report__why">
        <h4 className="vy-overline">Why it suits you</h4>
        <p className="vy-lead">Balanced proportions suit most cuts, and soft, muted shades suit a neutral undertone.</p>
        <Alert title="This is sample data">
          Values are illustrative and not from a real person or a real analysis. Real results are estimates from one photo; lighting and camera can shift them.
        </Alert>
      </div>
    </article>
  );
}
