'use client';

import { useEffect, useState } from 'react';
import { Alert, Badge } from '@vysel/ui';
import { ApiError } from '@/lib/api';
import type { Report, ReportListItem } from '@/lib/reports';

const ATTRIBUTES = [
  ['Face shape', 'face_shape'],
  ['Undertone', 'undertone'],
  ['Skin depth', 'skin_depth'],
  ['Feature contrast', 'contrast'],
] as const;

const CATEGORY_LABELS = {
  hair: 'Hair',
  eyewear: 'Eyewear',
  makeup: 'Makeup',
  outfit_color: 'Outfit colour',
  outfit_cut: 'Outfit cut',
} as const;

export function ReportComparison({
  left,
  right,
  loadReport,
}: {
  left: ReportListItem;
  right: ReportListItem;
  loadReport: (id: string) => Promise<Report>;
}) {
  const [reports, setReports] = useState<[Report, Report] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setReports(null);
    setError(null);
    Promise.all([loadReport(left.id), loadReport(right.id)])
      .then(([first, second]) => {
        if (active) setReports([first, second]);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof ApiError ? cause.message : 'Could not load reports for comparison.');
      });
    return () => { active = false; };
  }, [left.id, right.id, loadReport]);

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!reports) return <p className="vy-caption" role="status">Loading reports for comparison…</p>;

  return (
    <section className="history-compare" aria-label="Side-by-side Style DNA comparison">
      {reports.map((report) => (
        <article className="history-compare__column vy-card" key={report.id}>
          <header className="history-compare__header">
            <p className="vy-overline">{new Date(report.created_at).toLocaleDateString()}</p>
            <h3 className="vy-h4">{report.report_data.season.value} season</h3>
            <Badge tone="accent">Style DNA</Badge>
          </header>
          <section aria-label="Estimated attributes">
            <h4 className="vy-label">Estimated attributes</h4>
            <dl className="history-compare__attributes">
              {ATTRIBUTES.map(([label, key]) => (
                <div key={key}>
                  <dt className="vy-caption">{label}</dt>
                  <dd>{report.report_data.features[key].value}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section aria-label="Colour palette">
            <h4 className="vy-label">Colour palette</h4>
            <div className="history-compare__palette">
              {report.report_data.palette.map((color) => (
                <span key={color.hex} className="history-compare__swatch" title={`${color.name} ${color.hex}`} style={{ backgroundColor: color.hex }} />
              ))}
            </div>
          </section>
          <section className="history-compare__recommendations" aria-label="Recommendations">
            <h4 className="vy-label">Recommendations</h4>
            {report.report_data.recommendations.map((group) => (
              <div key={group.category}>
                <h5 className="vy-caption">{CATEGORY_LABELS[group.category]}</h5>
                <ul>
                  {group.items.map((item) => <li key={item.id}>{item.label} · {Math.round(item.score * 100)}%</li>)}
                </ul>
              </div>
            ))}
          </section>
        </article>
      ))}
    </section>
  );
}
