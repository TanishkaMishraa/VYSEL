'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Alert, Button } from '@vysel/ui';
import { ReportView } from '@/components/reports/ReportView';
import { api, ApiError } from '@/lib/api';
import type { Recommendations } from '@/lib/reports';

export default function SharedReportPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Recommendations | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Recommendations>(`/reports/shared/${encodeURIComponent(token)}`)
      .then(setData)
      .catch((cause: unknown) => setError(cause instanceof ApiError ? cause.message : 'This shared report is unavailable.'));
  }, [token]);

  return (
    <main className="shared-report">
      <div className="report-page__actions screen-only">
        <a className="vy-nav__brand" href="/">VYSEL</a>
        <Button variant="secondary" onClick={() => window.print()}>Print / Save as PDF</Button>
      </div>
      {error && <Alert tone="danger" title="Report unavailable">{error}</Alert>}
      {!data && !error && <p className="vy-body">Loading shared report…</p>}
      {data && <ReportView data={data} />}
    </main>
  );
}
