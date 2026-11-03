'use client';

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { cx } from '../cx';
import { Wordmark } from '../brand/Wordmark';
import { Button } from './Button';
import { Icon } from './Icon';

export interface NavLink {
  href: string;
  label: string;
  current?: boolean;
}

export interface NavBarProps {
  links: NavLink[];
  actions?: ReactNode;
  homeHref?: string;
  /** Swap in Next.js <Link> without adding a Next dependency here. */
  renderLink?: (link: NavLink & { className: string; children: ReactNode }) => ReactNode;
}

export function NavBar({ links, actions, homeHref = '/', renderLink }: NavBarProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const linkEl = (l: NavLink) => {
    const className = 'vy-nav__link';
    if (renderLink) return renderLink({ ...l, className, children: l.label });
    return (
      <a href={l.href} className={className} aria-current={l.current ? 'page' : undefined}>
        {l.label}
      </a>
    );
  };

  return (
    <header className="vy-nav" data-open={open}>
      <nav className="vy-container vy-nav__inner" aria-label="Primary">
        <a href={homeHref} className="vy-nav__brand" aria-label="VYSEL home">
          <Wordmark />
        </a>
        <Button
          variant="ghost"
          iconOnly
          className="vy-nav__toggle"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((o) => !o)}
        >
          <Icon name={open ? 'close' : 'menu'} />
        </Button>
        {/* Close the mobile menu once a destination is chosen. */}
        <ul className="vy-nav__links" id={menuId} onClick={(e) => (e.target as HTMLElement).closest('a') && setOpen(false)}>
          {links.map((l) => (
            <li key={l.href}>{linkEl(l)}</li>
          ))}
        </ul>
        {actions && <div className="vy-nav__actions">{actions}</div>}
      </nav>
    </header>
  );
}

export interface TabItem {
  id: string;
  label: ReactNode;
  content: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  label: string;
  defaultTab?: string;
  /** Vertical lists use ArrowUp/ArrowDown and sit beside the panel from md up. */
  orientation?: 'horizontal' | 'vertical';
  onChange?: (id: string) => void;
  className?: string;
}

/** WAI-ARIA Tabs: arrow keys move between tabs, Home/End jump, automatic activation. */
export function Tabs({ items, label, defaultTab, orientation = 'horizontal', onChange, className }: TabsProps) {
  const [active, setActiveState] = useState(defaultTab ?? items[0]?.id);
  const baseId = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const setActive = (id: string) => {
    setActiveState(id);
    onChange?.(id);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = items.findIndex((t) => t.id === active);
    const [prev, next] = orientation === 'vertical' ? ['ArrowUp', 'ArrowDown'] : ['ArrowLeft', 'ArrowRight'];
    const target = { [next]: i + 1, [prev]: i - 1, Home: 0, End: items.length - 1 }[e.key];
    if (target === undefined) return;
    e.preventDefault();
    const j = (target + items.length) % items.length;
    setActive(items[j].id);
    tabRefs.current[j]?.focus();
  };

  return (
    <div className={cx('vy-tabs', orientation === 'vertical' && 'vy-tabs--vertical', className)}>
      <div className="vy-tabs__list" role="tablist" aria-label={label} aria-orientation={orientation} onKeyDown={onKeyDown}>
        {items.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[i] = el;
            }}
            role="tab"
            type="button"
            id={`${baseId}-tab-${t.id}`}
            className="vy-tabs__tab"
            aria-selected={t.id === active}
            aria-controls={`${baseId}-panel-${t.id}`}
            tabIndex={t.id === active ? 0 : -1}
            onClick={() => setActive(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {items.map((t) => (
        <div
          key={t.id}
          role="tabpanel"
          id={`${baseId}-panel-${t.id}`}
          aria-labelledby={`${baseId}-tab-${t.id}`}
          className="vy-tabs__panel"
          hidden={t.id !== active}
          tabIndex={0}
        >
          {t.content}
        </div>
      ))}
    </div>
  );
}
