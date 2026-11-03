'use client';

import { useEffect, useState } from 'react';
import { Alert, Badge, StateMessage } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { useAuth } from '@/components/auth/AuthProvider';
import { RequireAuth } from '@/components/auth/guards';
import { ApiError } from '@/lib/api';
import type { AdminOverview } from '@/lib/admin';

function AdminDashboard() {
  const { user, apiRequest } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.is_admin) return;
    apiRequest<AdminOverview>('/admin/overview')
      .then(setOverview)
      .catch((cause: unknown) => setError(cause instanceof ApiError ? cause.message : 'Could not load admin metrics.'));
  }, [apiRequest, user?.is_admin]);

  if (!user?.is_admin) {
    return (
      <AppShell narrow>
        <StateMessage kind="error" title="Administrator access required" description="This dashboard is available only to accounts approved by VYSEL." />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-8 py-8">
        <header className="space-y-2">
          <p className="vy-overline">Operations</p>
          <h1 className="vy-h2">Admin dashboard</h1>
          <p className="vy-body">Account, scan, and recommendation health. Private image content is never shown here.</p>
        </header>

        {error && <Alert tone="danger" title="Could not load dashboard">{error}</Alert>}
        {!overview && !error && <p className="vy-caption" role="status">Loading dashboard metrics…</p>}
        {overview && (
          <>
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Platform totals">
              <Metric title="Registered users" value={overview.registered_users} />
              <Metric title="Style analyses" value={overview.analyses} />
              <Metric title="Scans" value={overview.scans.total} detail={`${overview.scans.succeeded} succeeded · ${overview.scans.failed} failed`} />
              <Metric title="Recommendation feedback" value={overview.feedback_total} />
            </section>

            <section className="vy-card space-y-4 p-6" aria-labelledby="accuracy-heading">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="vy-h4" id="accuracy-heading">Model evaluation</h2>
                <Badge tone="neutral">Not available</Badge>
              </div>
              <p className="vy-body">{overview.model_evaluation.message}</p>
              <p className="vy-caption">Accuracy: unavailable · Macro F1: unavailable · Evaluation samples: {overview.model_evaluation.sample_count}</p>
            </section>

            <section className="vy-card space-y-4 p-6" aria-labelledby="scans-heading">
              <h2 className="vy-h4" id="scans-heading">Scan health</h2>
              <div className="flex flex-wrap gap-2">
                {(['queued', 'running', 'succeeded', 'failed'] as const).map((status) => (
                  <Badge key={status} tone={status === 'failed' && overview.scans.failed > 0 ? 'warning' : 'neutral'}>
                    {status}: {overview.scans[status]}
                  </Badge>
                ))}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Scan counts by model version</caption>
                  <thead><tr><th className="py-2 pr-4">Model version</th><th>Status counts</th></tr></thead>
                  <tbody>
                    {Object.entries(overview.scans.model_versions).map(([version, counts]) => (
                      <tr key={version} className="border-t border-[var(--vy-color-border,#ddd)]">
                        <th scope="row" className="py-2 pr-4 font-medium">{version}</th>
                        <td>{Object.entries(counts).map(([status, count]) => `${status}: ${count}`).join(' · ')}</td>
                      </tr>
                    ))}
                    {Object.keys(overview.scans.model_versions).length === 0 && <tr><td className="py-2" colSpan={2}>No scans recorded.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="vy-card space-y-4 p-6" aria-labelledby="users-heading">
              <h2 className="vy-h4" id="users-heading">Recently registered users</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="py-2 pr-4">Name</th><th className="py-2 pr-4">Email</th><th className="py-2 pr-4">Verified</th><th>Registered</th></tr></thead>
                  <tbody>
                    {overview.recent_users.map((item) => (
                      <tr key={item.id} className="border-t border-[var(--vy-color-border,#ddd)]">
                        <td className="py-2 pr-4">{item.display_name}</td><td className="py-2 pr-4">{item.email}</td>
                        <td className="py-2 pr-4">{item.email_verified ? 'Yes' : 'No'}</td>
                        <td>{new Date(item.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                    {overview.recent_users.length === 0 && <tr><td className="py-2" colSpan={4}>No registered users.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <MetricTable
                title="Recommendation feedback"
                headers={['Category', 'Helpful', 'Not helpful']}
                rows={overview.feedback.map((item) => [item.category, String(item.helpful), String(item.not_helpful)])}
                empty="No feedback has been submitted."
              />
              <MetricTable
                title="Recent system failures"
                headers={['Source', 'Category', 'Status', 'Occurred']}
                rows={overview.system_failures.map((item) => [item.source, item.category, item.status, new Date(item.occurred_at).toLocaleString()])}
                empty="No recent failures."
              />
            </section>

            <section className="vy-card space-y-4 p-6" aria-labelledby="flagged-heading">
              <h2 className="vy-h4" id="flagged-heading">Flagged scan metadata</h2>
              <p className="vy-caption">Only scan and validation metadata is displayed; image bytes and biometric payloads remain private.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="py-2 pr-4">Scan ID</th><th className="py-2 pr-4">Status</th><th className="py-2 pr-4">Issue codes</th><th>Created</th></tr></thead>
                  <tbody>
                    {overview.flagged_images.map((item) => (
                      <tr key={item.scan_id} className="border-t border-[var(--vy-color-border,#ddd)]">
                        <td className="py-2 pr-4">{item.scan_id}</td><td className="py-2 pr-4">{item.status}</td>
                        <td className="py-2 pr-4">{[item.error_code, ...item.quality_flags, ...item.warning_codes].filter(Boolean).join(', ') || '—'}</td>
                        <td>{new Date(item.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                    {overview.flagged_images.length === 0 && <tr><td className="py-2" colSpan={4}>No flagged scans.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}

function Metric({ title, value, detail }: { title: string; value: number; detail?: string }) {
  return (
    <article className="vy-card space-y-2 p-5">
      <p className="vy-overline">{title}</p>
      <p className="vy-h3">{value.toLocaleString()}</p>
      {detail && <p className="vy-caption">{detail}</p>}
    </article>
  );
}

function MetricTable({ title, headers, rows, empty }: { title: string; headers: string[]; rows: string[][]; empty: string }) {
  return (
    <section className="vy-card space-y-4 p-6">
      <h2 className="vy-h4">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead><tr>{headers.map((header) => <th key={header} className="py-2 pr-4">{header}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => <tr key={`${row[0]}-${index}`} className="border-t border-[var(--vy-color-border,#ddd)]">{row.map((cell, cellIndex) => <td key={cellIndex} className="py-2 pr-4">{cell}</td>)}</tr>)}
            {rows.length === 0 && <tr><td className="py-2" colSpan={headers.length}>{empty}</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AdminPage() {
  return <RequireAuth><AdminDashboard /></RequireAuth>;
}
