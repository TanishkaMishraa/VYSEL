import type { HTMLAttributes, ReactNode } from 'react';
import { cx } from '../cx';

export type CardVariant = 'default' | 'raised' | 'gilded';

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  variant?: CardVariant;
  /** Adds hover lift. Render as a link/button via `as` for real interactivity. */
  interactive?: boolean;
  as?: 'div' | 'article' | 'section' | 'a' | 'li';
  href?: string;
  eyebrow?: ReactNode;
  title?: ReactNode;
  footer?: ReactNode;
  media?: ReactNode;
}

export function Card({ variant = 'default', interactive, as: Tag = 'div', eyebrow, title, footer, media, className, children, ...rest }: CardProps) {
  return (
    <Tag
      className={cx('vy-card', variant !== 'default' && `vy-card--${variant}`, interactive && 'vy-card--interactive', className)}
      {...rest}
    >
      {media && <div className="vy-card__media">{media}</div>}
      {eyebrow && <p className="vy-overline">{eyebrow}</p>}
      {title && <h3 className="vy-card__title">{title}</h3>}
      {typeof children === 'string' ? <p className="vy-card__body">{children}</p> : children}
      {footer && <div className="vy-card__footer">{footer}</div>}
    </Tag>
  );
}
