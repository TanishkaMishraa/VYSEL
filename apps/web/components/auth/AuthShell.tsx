import Link from 'next/link';
import type { ReactNode } from 'react';
import { Wordmark } from '@vysel/ui';
import { FaceMap } from '@/components/landing/FaceMap';
import './auth.css';

/** Split editorial layout for sign-in flows: brand panel (≥1024px) + form column. */
export function AuthShell({ eyebrow, title, lead, children, footer }: { eyebrow: string; title: ReactNode; lead?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="au-shell">
      <aside className="au-panel" aria-hidden="true">
        <Link href="/" className="au-panel__brand" tabIndex={-1}>
          <Wordmark title={null} />
        </Link>
        <FaceMap labels={false} className="au-panel__map" />
        <p className="vy-lead">Style advice built from your face, not a trend list.</p>
      </aside>
      <main id="main" className="au-main">
        <Link href="/" className="au-main__brand" aria-label="VYSEL home">
          <Wordmark title={null} />
        </Link>
        <div className="au-form">
          <header className="flex flex-col gap-3">
            <p className="vy-overline">{eyebrow}</p>
            <h1 className="vy-h3">{title}</h1>
            {lead && <p className="vy-caption">{lead}</p>}
          </header>
          {children}
          {footer && <div className="au-form__footer">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
