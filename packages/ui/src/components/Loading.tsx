import type { CSSProperties, ReactNode } from 'react';
import { cx } from '../cx';
import { Icon } from './Icon';

export function Spinner({ size = 'md', label = 'Loading' }: { size?: 'md' | 'lg'; label?: string | null }) {
  return (
    <span
      className={cx('vy-spinner', size === 'lg' && 'vy-spinner--lg')}
      role={label ? 'status' : undefined}
      aria-label={label ?? undefined}
      aria-hidden={label ? undefined : true}
    />
  );
}

export function Skeleton({ width, height, circle, className }: { width?: string; height?: string; circle?: boolean; className?: string }) {
  return <span className={cx('vy-skeleton', circle && 'vy-skeleton--circle', className)} style={{ width, height }} aria-hidden="true" />;
}

export function Progress({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="vy-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={v}>
      <div className="vy-progress__bar" style={{ '--vy-value': v } as CSSProperties} />
    </div>
  );
}

export type StepState = 'pending' | 'active' | 'done' | 'error';
export interface StepItem {
  id: string;
  label: ReactNode;
  state: StepState;
}

/**
 * Analysis progress. Map API `AnalysisStage` values to steps:
 * quality_check → landmarks → face_geometry → skin_tone → recommendations → finalizing.
 */
export function Steps({ items, label = 'Analysis progress' }: { items: StepItem[]; label?: string }) {
  const active = items.find((s) => s.state === 'active');
  return (
    <>
      <ol className="vy-steps" aria-label={label}>
        {items.map((s, i) => (
          <li key={s.id} className="vy-steps__item" data-state={s.state} aria-current={s.state === 'active' ? 'step' : undefined}>
            <span className="vy-steps__marker" aria-hidden="true">
              {s.state === 'done' ? <Icon name="check" /> : s.state === 'error' ? <Icon name="close" /> : i + 1}
            </span>
            <span>
              {s.label}
              <span className="vy-visually-hidden"> — {s.state}</span>
            </span>
          </li>
        ))}
      </ol>
      {/* Announce stage changes without re-reading the whole list. */}
      <p className="vy-visually-hidden" aria-live="polite">
        {active ? active.label : ''}
      </p>
    </>
  );
}
