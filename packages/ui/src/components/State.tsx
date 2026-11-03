import type { ReactNode } from 'react';
import { cx } from '../cx';
import { Icon, type IconName } from './Icon';

export type StateKind = 'empty' | 'success' | 'error' | 'info';

const DEFAULT_ICON: Record<StateKind, IconName> = { empty: 'facet', success: 'check', error: 'alert', info: 'info' };

export interface StateMessageProps {
  kind: StateKind;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: IconName;
  className?: string;
}

/** Full-area state: empty lists, completed flows, failed loads. Errors are announced. */
export function StateMessage({ kind, title, description, actions, icon, className }: StateMessageProps) {
  return (
    <section className={cx('vy-state', `vy-state--${kind}`, className)} role={kind === 'error' ? 'alert' : 'status'}>
      <span className="vy-state__icon" aria-hidden="true">
        <Icon name={icon ?? DEFAULT_ICON[kind]} />
      </span>
      <h2 className="vy-state__title">{title}</h2>
      {description && <p className="vy-state__desc">{description}</p>}
      {actions && <div className="vy-state__actions">{actions}</div>}
    </section>
  );
}

export type AlertTone = 'info' | 'success' | 'warning' | 'danger';
const ALERT_ICON: Record<AlertTone, IconName> = { info: 'info', success: 'check', warning: 'alert', danger: 'alert' };

/** Inline, compact message for forms and banners. */
export function Alert({ tone = 'info', title, children, className }: { tone?: AlertTone; title?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div
      className={cx('vy-alert', tone !== 'info' && `vy-alert--${tone}`, className)}
      role={tone === 'danger' || tone === 'warning' ? 'alert' : 'status'}
    >
      <span className="vy-alert__icon" aria-hidden="true">
        <Icon name={ALERT_ICON[tone]} />
      </span>
      <div>
        {title && <p className="vy-alert__title">{title}</p>}
        {children && <p className="vy-alert__body">{children}</p>}
      </div>
    </div>
  );
}
