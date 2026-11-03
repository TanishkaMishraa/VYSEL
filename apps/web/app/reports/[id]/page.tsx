'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Alert, Button, buttonClassName } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { RequireAuth } from '@/components/auth/guards';
import { useAuth } from '@/components/auth/AuthProvider';
import { ReportView } from '@/components/reports/ReportView';
import { ApiError } from '@/lib/api';
import { downloadReportPdf } from '@/lib/reportPdf';
import type { Report } from '@/lib/reports';

function ReportPageContent() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { apiRequest } = useAuth();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    apiRequest<Report>(`/reports/${encodeURIComponent(id)}`)
      .then(setReport)
      .catch((cause: unknown) => setError(cause instanceof ApiError ? cause.message : 'Could not load this report.'));
  }, [apiRequest, id]);

  const feedback = useMemo(
    () => Object.fromEntries((report?.feedback ?? []).map((item) => [item.recommendation_id, item.helpful])),
    [report?.feedback],
  );

  async function saveFeedback(recommendationId: string, helpful: boolean) {
    try {
      const saved = await apiRequest<{ recommendation_id: string; helpful: boolean; updated_at: string }>(
        `/reports/${encodeURIComponent(id)}/feedback`,
        { method: 'PUT', json: { recommendation_id: recommendationId, helpful } },
      );
      setReport((current) => current && ({
        ...current,
        feedback: [...current.feedback.filter((item) => item.recommendation_id !== saved.recommendation_id), saved],
      }));
      setNotice('Thanks, your feedback was saved.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not save your feedback.');
    }
  }

  async function enableSharing() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<{ share_url: string }>(`/reports/${encodeURIComponent(id)}/share`, { method: 'POST' });
      setShareUrl(`${window.location.origin}${result.share_url}`);
      setReport((current) => current && ({ ...current, share_enabled: true }));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not create a share link.');
    } finally {
      setBusy(false);
    }
  }

  async function disableSharing() {
    setBusy(true);
    setError(null);
    try {
      await apiRequest(`/reports/${encodeURIComponent(id)}/share`, { method: 'DELETE' });
      setShareUrl(null);
      setReport((current) => current && ({ ...current, share_enabled: false }));
      setNotice('Sharing is off. The previous link no longer works.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not turn off sharing.');
    } finally {
      setBusy(false);
    }
  }

  async function copyShareLink() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setNotice('Share link copied.');
    } catch {
      setError('Could not access the clipboard. Select and copy the share link instead.');
    }
  }

  async function deleteReport() {
    if (!window.confirm('Delete this report? Its share link and feedback will also be removed.')) return;
    setBusy(true);
    try {
      await apiRequest(`/reports/${encodeURIComponent(id)}`, { method: 'DELETE' });
      router.replace('/dashboard');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not delete the report.');
      setBusy(false);
    }
  }

  async function exportPdf() {
    if (!report) return;
    setPdfBusy(true);
    setError(null);
    try {
      downloadReportPdf(report.report_data, report.id, report.created_at);
      setNotice('Your PDF download has started.');
    } catch (cause) {
      setError(cause instanceof Error ? `Could not create the PDF: ${cause.message}` : 'Could not create the PDF. Please try again.');
    } finally {
      setPdfBusy(false);
    }
  }

  if (!report && !error) return <p className="vy-body">Loading your report…</p>;
  return (
    <div className="report-page">
      <div className="report-page__actions screen-only">
        <Link href="/dashboard" className={buttonClassName({ variant: 'link' })}>Back to dashboard</Link>
        <Button variant="secondary" disabled={pdfBusy} loading={pdfBusy} onClick={exportPdf}>Download PDF</Button>
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {report && (
        <>
          <ReportView data={report.report_data} feedback={feedback} onFeedback={saveFeedback} />
          <section className="report-page__sharing vy-card screen-only" aria-labelledby="report-share-title">
            <div>
              <p className="vy-overline">Privacy controls</p>
              <h2 className="vy-h4" id="report-share-title">Share this report</h2>
              <p className="vy-caption">{report.share_enabled ? 'A public link is active. Anyone with the link can view this report.' : 'Private by default. Create a public link only when you choose to share.'}</p>
            </div>
            <div className="report-page__share-actions">
              <Button variant="secondary" disabled={busy} onClick={enableSharing}>
                {shareUrl ? 'Create a new link' : report.share_enabled ? 'Create a replacement link' : 'Enable sharing'}
              </Button>
              {report.share_enabled && <Button variant="ghost" disabled={busy} onClick={disableSharing}>Revoke link</Button>}
            </div>
            {shareUrl && (
              <div className="report-page__share-link">
                <label className="vy-label" htmlFor="share-link">Share link</label>
                <input id="share-link" className="vy-input" readOnly value={shareUrl} onFocus={(event) => event.currentTarget.select()} />
                <Button variant="secondary" onClick={copyShareLink}>Copy link</Button>
              </div>
            )}
          </section>
          <div className="report-page__delete screen-only">
            <Button variant="ghost" disabled={busy} onClick={deleteReport}>Delete report</Button>
          </div>
        </>
      )}
    </div>
  );
}

export default function ReportPage() {
  return <RequireAuth><AppShell><ReportPageContent /></AppShell></RequireAuth>;
}
