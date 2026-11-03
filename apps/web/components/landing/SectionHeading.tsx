import type { ReactNode } from 'react';

export function SectionHeading({ eyebrow, title, lead, id, center }: { eyebrow: string; title: ReactNode; lead?: ReactNode; id: string; center?: boolean }) {
  return (
    <header className={['lp-heading', center && 'lp-heading--center'].filter(Boolean).join(' ')}>
      <p className="vy-overline">{eyebrow}</p>
      <h2 className="vy-h2" id={id}>
        {title}
      </h2>
      {lead && <p className="vy-lead">{lead}</p>}
    </header>
  );
}
