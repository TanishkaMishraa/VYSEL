'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Alert, Badge, StateMessage, buttonClassName } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { useAuth } from '@/components/auth/AuthProvider';
import { RequireAuth } from '@/components/auth/guards';
import { BUDGETS, OCCASIONS, STYLE_GOALS, STYLES, labelOf } from '@/lib/preferences';
import { ApiError } from '@/lib/api';
import type { ReportListItem } from '@/lib/reports';

function Dashboard() {
  const { user, apiRequest } = useAuth();
  const [reports, setReports] = useState<ReportListItem[] | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const preferences = user!.preferences;
  const goals = preferences.style_goals.map((goal) => labelOf(STYLE_GOALS, goal)!);
  const occasions = preferences.occasions.map((occasion) => labelOf(OCCASIONS, occasion)!);

  useEffect(() => {
    apiRequest<ReportListItem[]>('/reports')
      .then(setReports)
      .catch((cause: unknown) => setReportError(cause instanceof ApiError ? cause.message : 'Could not load your reports.'));
  }, [apiRequest]);

  return (
    <div className="dash">
      <header className="dash__heading">
        <div>
          <p className="vy-overline">Your VYSEL space</p>
          <h1 className="vy-h2">
            Welcome, <span className="vy-emphasis">{user!.display_name}</span>
          </h1>
          <p className="vy-body">Your style goals and account, together in one place.</p>
        </div>
        {user!.onboarding_completed && <Badge tone="success">Profile ready</Badge>}
      </header>

      {!user!.onboarding_completed && (
        <Alert tone="info" title="Personalise your Style DNA">
          Tell us what you’re looking for, where you’ll wear it, and your budget.
          {' '}<Link href="/onboarding">Complete your questionnaire</Link>
        </Alert>
      )}

      <section className="dash__feature vy-card" aria-labelledby="dash-scan-title">
        <div className="dash__feature-copy">
          <p className="vy-overline">Your next step</p>
          <h2 className="vy-h3" id="dash-scan-title">Create a Style DNA report</h2>
          <p className="vy-body">Choose your own feature estimates to get personalised colour, hair, eyewear, makeup, and outfit suggestions. Your photo is never uploaded.</p>
          <Link href="/scan" className={buttonClassName()}>
            <span className="vy-btn__label">Create a report</span>
          </Link>
        </div>
        <div className="dash__feature-mark" aria-hidden="true">
          <span className="dash__face" />
          <span className="dash__orbit dash__orbit--one" />
          <span className="dash__orbit dash__orbit--two" />
        </div>
      </section>

      <section className="dash__section" aria-labelledby="dash-reports-title">
        <div className="dash__section-head">
          <div>
            <p className="vy-overline">Your saved style reports</p>
            <h2 className="vy-h4" id="dash-reports-title">Style DNA history</h2>
          </div>
          <Link href="/scan" className={buttonClassName({ variant: 'secondary' })}>
            <span className="vy-btn__label">New report</span>
          </Link>
        </div>
        {reportError && <Alert tone="danger">{reportError}</Alert>}
        {reports === null ? (
          <p className="vy-caption">Loading your saved reports…</p>
        ) : reports.length > 0 ? (
          <div className="dash__reports">
            {reports.map((report) => (
              <article className="dash__report vy-card" key={report.id}>
                <div>
                  <p className="vy-overline">{report.season} season</p>
                  <p className="vy-caption">{new Date(report.created_at).toLocaleDateString()} · {report.recommendation_count} recommendations</p>
                </div>
                <div className="dash__report-actions">
                  {report.share_enabled && <Badge tone="accent">Shared</Badge>}
                  <Link href={`/reports/${encodeURIComponent(report.id)}`} className={buttonClassName({ variant: 'link' })}>
                    <span className="vy-btn__label">View report</span>
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <StateMessage
            kind="empty"
            title="Your reports will appear here"
            description="Create a Style DNA report to save your first set of recommendations."
            actions={<Link href="/scan" className={buttonClassName()}><span className="vy-btn__label">Create report</span></Link>}
          />
        )}
      </section>

      <section className="dash__section" aria-labelledby="dash-goals-title">
        <div className="dash__section-head">
          <div>
            <p className="vy-overline">Saved to your profile</p>
            <h2 className="vy-h4" id="dash-goals-title">Your style preferences</h2>
          </div>
          <Link href="/settings" className={buttonClassName({ variant: 'link' })}>
            <span className="vy-btn__label">Manage settings</span>
          </Link>
        </div>
        {user!.onboarding_completed ? (
          <div className="dash__preferences">
            <article className="vy-card dash__preference">
              <h3 className="vy-overline">Style goals</h3>
              <div className="flex flex-wrap gap-2">
                {goals.length ? goals.map((goal) => <Badge key={goal} tone="accent">{goal}</Badge>) : <span className="vy-caption">No goals selected</span>}
              </div>
            </article>
            <article className="vy-card dash__preference">
              <h3 className="vy-overline">Occasions</h3>
              <div className="flex flex-wrap gap-2">
                {occasions.length ? occasions.map((occasion) => <Badge key={occasion}>{occasion}</Badge>) : <span className="vy-caption">No occasions selected</span>}
              </div>
            </article>
            <article className="vy-card dash__preference">
              <h3 className="vy-overline">Budget & style</h3>
              <div className="flex flex-wrap gap-2">
                {preferences.budget && <Badge>{labelOf(BUDGETS, preferences.budget)}</Badge>}
                {preferences.style && <Badge>{labelOf(STYLES, preferences.style)}</Badge>}
                {!preferences.budget && !preferences.style && <span className="vy-caption">Not set</span>}
              </div>
            </article>
          </div>
        ) : (
          <StateMessage
            kind="empty"
            title="Your preferences will show here"
            description="Complete the questionnaire to save your goals, occasions, and budget."
            actions={
              <Link href="/onboarding" className={buttonClassName()}>
                <span className="vy-btn__label">Set my preferences</span>
              </Link>
            }
          />
        )}
      </section>

      <section className="dash__account vy-card" aria-labelledby="dash-account-title">
        <div>
          <p className="vy-overline">Signed in as</p>
          <h2 className="vy-h4" id="dash-account-title">{user!.display_name}</h2>
          <p className="vy-caption">{user!.email}</p>
        </div>
        <Link href="/settings" className={buttonClassName({ variant: 'secondary' })}>
          <span className="vy-btn__label">Account settings</span>
        </Link>
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <AppShell>
        <Dashboard />
      </AppShell>
    </RequireAuth>
  );
}
