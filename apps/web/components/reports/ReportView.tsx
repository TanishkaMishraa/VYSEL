'use client';

import { Badge } from '@vysel/ui';
import type { Recommendations, RecommendationCategory } from '@/lib/reports';

const CATEGORY_LABELS: Record<RecommendationCategory, string> = {
  hair: 'Hair',
  eyewear: 'Eyewear',
  makeup: 'Makeup',
  outfit_color: 'Outfit colours',
  outfit_cut: 'Outfit cuts',
};

const FEATURE_LABELS = [
  ['Face shape', 'face_shape'],
  ['Undertone', 'undertone'],
  ['Skin depth', 'skin_depth'],
  ['Feature contrast', 'contrast'],
] as const;

export function ReportView({
  data,
  feedback = {},
  onFeedback,
}: {
  data: Recommendations;
  feedback?: Record<string, boolean>;
  onFeedback?: (recommendationId: string, helpful: boolean) => void;
}) {
  return (
    <article className="style-report">
      <header className="style-report__header">
        <div>
          <p className="vy-overline">Your Style DNA</p>
          <h1 className="vy-h2">A palette that feels like you.</h1>
          <p className="vy-body">Personalised styling ideas, based on the estimates you provided.</p>
        </div>
        <Badge tone="accent">{data.season.value} season · provisional</Badge>
      </header>

      <section className="style-report__section" aria-labelledby="report-estimates-title">
        <div>
          <p className="vy-overline">Your inputs</p>
          <h2 className="vy-h4" id="report-estimates-title">Estimated features</h2>
        </div>
        <dl className="style-report__features">
          {FEATURE_LABELS.map(([label, key]) => {
            const estimate = data.features[key];
            return (
              <div className="style-report__feature" key={key}>
                <dt className="vy-caption">{label}</dt>
                <dd><strong>{estimate.value}</strong><span>{Math.round(estimate.confidence * 100)}% confidence</span></dd>
              </div>
            );
          })}
        </dl>
        <p className="vy-caption">{data.season.rationale} Seasonal palette confidence: {Math.round(data.season.confidence * 100)}%.</p>
      </section>

      <section className="style-report__section" aria-labelledby="report-palette-title">
        <div>
          <p className="vy-overline">Your colours</p>
          <h2 className="vy-h4" id="report-palette-title">{data.season.value} palette</h2>
        </div>
        <div className="style-report__palette">
          {data.palette.map((color) => (
            <article className="style-report__swatch" key={`${color.name}-${color.hex}`}>
              <span className="style-report__color" style={{ backgroundColor: color.hex }} aria-label={`${color.name} swatch`} />
              <strong>{color.name}</strong>
              <span className="vy-caption">{color.hex} · {color.role}</span>
              <p className="vy-caption">{color.wear}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="style-report__section" aria-labelledby="report-recommendations-title">
        <div>
          <p className="vy-overline">Made for your preferences</p>
          <h2 className="vy-h4" id="report-recommendations-title">Your recommendations</h2>
        </div>
        <div className="style-report__groups">
          {data.recommendations.map((group) => (
            <section className="style-report__group" key={group.category} aria-labelledby={`category-${group.category}`}>
              <h3 className="vy-h4" id={`category-${group.category}`}>{CATEGORY_LABELS[group.category]}</h3>
              <div className="style-report__cards">
                {group.items.map((item) => (
                  <article className="style-report__card vy-card" key={item.id}>
                    <div className="style-report__card-top">
                      <h4 className="vy-h4">{item.label}</h4>
                      <Badge>{Math.round(item.score * 100)}% match</Badge>
                    </div>
                    <p className="vy-body">{item.reason}</p>
                    <p className="vy-caption">
                      Budget: {item.budget}{item.within_budget === true ? ' · within your budget' : item.within_budget === false ? ' · above your saved budget' : ''}
                    </p>
                    {item.color_hex && <span className="style-report__recommendation-color" style={{ backgroundColor: item.color_hex }} aria-label={`Suggested colour ${item.color_hex}`} />}
                    {onFeedback && (
                      <div className="style-report__feedback" aria-label={`Was ${item.label} helpful?`}>
                        <span className="vy-caption">Helpful?</span>
                        <button type="button" className="style-report__vote" aria-pressed={feedback[item.id] === true} onClick={() => onFeedback(item.id, true)}>Yes</button>
                        <button type="button" className="style-report__vote" aria-pressed={feedback[item.id] === false} onClick={() => onFeedback(item.id, false)}>No</button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>

      <aside className="style-report__disclaimer">
        <p className="vy-caption">{data.disclaimer}</p>
        <p className="vy-caption">This report is generated from self-selected estimates and profile preferences. It is not facial analysis or professional advice.</p>
      </aside>
    </article>
  );
}
