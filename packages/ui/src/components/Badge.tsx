import type { HTMLAttributes } from 'react';
import { cx } from '../cx';

export type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info' | 'estimate';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
}

/**
 * Status label. `tone="estimate"` (dashed) marks any AI-inferred value —
 * required wherever the UI shows face shape, undertone or skin tone.
 */
export function Badge({ tone = 'neutral', dot, className, children, ...rest }: BadgeProps) {
  return (
    <span className={cx('vy-badge', tone !== 'neutral' && `vy-badge--${tone}`, className)} {...rest}>
      {dot && <span className="vy-badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function EstimateBadge({ confidence }: { confidence?: number }) {
  const pct = confidence === undefined ? undefined : Math.round(confidence * 100);
  return (
    <Badge tone="estimate" title="Estimated from your photo — lighting and camera can shift results.">
      Estimate{pct !== undefined && <span className="vy-numeric"> · {pct}%</span>}
    </Badge>
  );
}
