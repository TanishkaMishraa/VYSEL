'use client';

import { useEffect, useState } from 'react';
import { Spinner } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { useAuth } from '@/components/auth/AuthProvider';
import { SiteNav } from '@/components/landing/SiteChrome';
import { TryOnStudio } from '@/components/tryon/TryOnStudio';
import type { Report, ReportListItem } from '@/lib/reports';
import { STARTER_SHADES, shadesFromReport, type ShadeSet } from '@/lib/tryon/shades';
import './tryon.css';

/** Virtual try-on. Signed-in users get shades from their latest Style DNA; guests get starter shades. */
export default function TryOnPage() {
  const { status, apiRequest } = useAuth();
  const [shades, setShades] = useState<ShadeSet | null>(null);

  useEffect(() => {
    if (status === 'loading') return;
    if (status === 'anonymous') return setShades(STARTER_SHADES);
    let cancelled = false;
    (async () => {
      try {
        const [latest] = await apiRequest<ReportListItem[]>('/reports');
        const set = latest ? shadesFromReport(await apiRequest<Report>(`/reports/${latest.id}`)) : STARTER_SHADES;
        if (!cancelled) setShades(set);
      } catch {
        if (!cancelled) setShades(STARTER_SHADES); // try-on still works without recommendations
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, apiRequest]);

  const content = (
    <div className="to-page">
      <header className="to-page__head">
        <p className="vy-overline">Virtual try-on</p>
        <h1 className="vy-h2">
          Try your shades, <span className="vy-emphasis">live</span>
        </h1>
        <p className="vy-body">
          {shades?.source === 'style-dna'
            ? 'Lip, blush and liner shades from your Style DNA, mapped to your face in real time.'
            : 'Preview lip, blush and liner shades mapped to your face in real time.'}
        </p>
      </header>
      {shades ? (
        <TryOnStudio shades={shades} apiRequest={status === 'authenticated' ? apiRequest : undefined} />
      ) : (
        <div className="to-loading">
          <Spinner size="lg" label="Loading your shades" />
        </div>
      )}
    </div>
  );

  if (status === 'authenticated') return <AppShell>{content}</AppShell>;
  return (
    <>
      <SiteNav />
      <main id="main" className="vy-container">
        {content}
      </main>
    </>
  );
}
