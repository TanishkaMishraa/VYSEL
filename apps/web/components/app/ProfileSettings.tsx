'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent, type ReactNode } from 'react';
import { Alert, Badge, Button, Field, Input, Modal, buttonClassName } from '@vysel/ui';
import { useAuth, type ProfileUpdate } from '@/components/auth/AuthProvider';
import { ChoiceGrid } from '@/components/auth/ChoiceGrid';
import { ApiError } from '@/lib/api';
import { BUDGETS, OCCASIONS, STYLE_GOALS, STYLES, categoriesFor, labelOf, type Preferences } from '@/lib/preferences';

type Section = 'goals' | 'occasions' | 'budget' | 'style';

/** One preference group: shows the saved answer, or an inline editor. */
function PrefCard({
  title,
  summary,
  editing,
  onEdit,
  onCancel,
  onSave,
  saving,
  children,
}: {
  title: string;
  summary: string[];
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  saving: boolean;
  children: ReactNode;
}) {
  return (
    <section className="vy-card pf-card" aria-label={title}>
      <div className="pf-card__head">
        <h3 className="vy-overline">{title}</h3>
        {!editing && (
          <Button variant="link" onClick={onEdit}>
            Edit<span className="vy-visually-hidden"> {title.toLowerCase()}</span>
          </Button>
        )}
      </div>
      {editing ? (
        <>
          {children}
          <div className="flex gap-3">
            <Button size="sm" onClick={onSave} loading={saving}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        </>
      ) : summary.length ? (
        <div className="flex flex-wrap gap-2">
          {summary.map((s) => (
            <Badge key={s} tone="accent">
              {s}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="vy-caption">Not set yet</p>
      )}
    </section>
  );
}

function ProfileView() {
  const { user, updateProfile, deleteAccount } = useAuth();
  const router = useRouter();
  const saved = user!.preferences;
  const [draft, setDraft] = useState<Preferences>(saved);
  const [editing, setEditing] = useState<Section | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [name, setName] = useState(user!.display_name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function save(patch: ProfileUpdate, message: string) {
    setSaving(true);
    setNotice(null);
    try {
      const profile = await updateProfile(patch);
      setDraft(profile.preferences);
      setEditing(null);
      setNotice({ tone: 'success', text: message });
    } catch (e) {
      setNotice({ tone: 'danger', text: e instanceof ApiError ? e.message : 'Couldn’t save. Please try again.' });
    } finally {
      setSaving(false);
    }
  }

  const card = (section: Section) => ({
    editing: editing === section,
    saving,
    onEdit: () => {
      setDraft(saved);
      setEditing(section);
    },
    onCancel: () => {
      setDraft(saved);
      setEditing(null);
    },
  });

  function onSaveName(e: FormEvent) {
    e.preventDefault();
    if (name.trim() && name !== user!.display_name) save({ display_name: name.trim() }, 'Name updated.');
  }

  return (
    <div className="pf">
      <header className="flex flex-col gap-3">
        <p className="vy-overline">Your settings</p>
        <h1 className="vy-h2">
          Hello, <span className="vy-emphasis">{user!.display_name}</span>
        </h1>
      </header>

      {!user!.onboarding_completed && (
        <Alert tone="info" title="Finish your style questionnaire">
          It takes about a minute and tailors every recommendation. <Link href="/onboarding">Continue</Link>
        </Alert>
      )}
      <div aria-live="polite">{notice && <Alert tone={notice.tone}>{notice.text}</Alert>}</div>

      <section className="flex flex-col gap-5" aria-labelledby="prefs-title">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="vy-h4" id="prefs-title">
            Style preferences
          </h2>
          <Link href="/onboarding" className={buttonClassName({ variant: 'link' })}>
            <span className="vy-btn__label">Retake questionnaire</span>
          </Link>
        </div>
        <div className="pf-grid">
          <PrefCard
            title="Style goals"
            summary={saved.style_goals.map((g) => labelOf(STYLE_GOALS, g)!)}
            onSave={() => save({ preferences: { style_goals: draft.style_goals, categories: categoriesFor(draft.style_goals) } }, 'Style goals saved.')}
            {...card('goals')}
          >
            <ChoiceGrid legend="Style goals" name="pf-goals" multiple options={STYLE_GOALS} value={draft.style_goals} onChange={(v) => setDraft({ ...draft, style_goals: v })} />
          </PrefCard>
          <PrefCard
            title="Occasions"
            summary={saved.occasions.map((o) => labelOf(OCCASIONS, o)!)}
            onSave={() => save({ preferences: { occasions: draft.occasions } }, 'Occasions saved.')}
            {...card('occasions')}
          >
            <ChoiceGrid legend="Occasions" name="pf-occasions" multiple options={OCCASIONS} value={draft.occasions} onChange={(v) => setDraft({ ...draft, occasions: v })} />
          </PrefCard>
          <PrefCard
            title="Budget"
            summary={saved.budget ? [labelOf(BUDGETS, saved.budget)!] : []}
            onSave={() => save({ preferences: { budget: draft.budget } }, 'Budget saved.')}
            {...card('budget')}
          >
            <ChoiceGrid legend="Budget" name="pf-budget" options={BUDGETS} value={draft.budget} onChange={(v) => setDraft({ ...draft, budget: v })} />
          </PrefCard>
          <PrefCard
            title="Style"
            summary={saved.style ? [labelOf(STYLES, saved.style)!] : []}
            onSave={() => save({ preferences: { style: draft.style } }, 'Style saved.')}
            {...card('style')}
          >
            <ChoiceGrid legend="Style" name="pf-style" options={STYLES} value={draft.style} onChange={(v) => setDraft({ ...draft, style: v })} />
          </PrefCard>
        </div>
      </section>

      <section className="vy-card pf-account" aria-labelledby="account-title">
        <h2 className="vy-h4" id="account-title">
          Account
        </h2>
        <form className="pf-name" onSubmit={onSaveName}>
          <Field label="Display name">
            <Input value={name} maxLength={50} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Button type="submit" variant="secondary" disabled={!name.trim() || name === user!.display_name}>
            Save name
          </Button>
        </form>
        <dl className="pf-facts">
          <div>
            <dt className="vy-label">Email</dt>
            <dd>{user!.email}</dd>
          </div>
          <div>
            <dt className="vy-label">Sign-in methods</dt>
            <dd className="flex flex-wrap gap-2">
              {user!.auth_providers.map((p) => (
                <Badge key={p}>{p === 'google' ? 'Google' : 'Email & password'}</Badge>
              ))}
            </dd>
          </div>
        </dl>
        <div className="flex flex-wrap gap-4">
          <Link href="/forgot-password" className={buttonClassName({ variant: 'link' })}>
            <span className="vy-btn__label">{user!.has_password ? 'Change password' : 'Set a password'}</span>
          </Link>
          <Button variant="link" className="pf-danger" onClick={() => setConfirmDelete(true)}>
            Delete account
          </Button>
        </div>
      </section>

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete your account?"
        description="This permanently deletes your profile, reports, feedback, saved looks, scans, and private selfie files. If a private file cannot be removed, deletion stops so you can retry. This can’t be undone."
        dismissible={false}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)} disabled={deleting}>
              Keep my account
            </Button>
            <Button
              variant="secondary"
              loading={deleting}
              onClick={async () => {
                setDeleting(true);
                try {
                  await deleteAccount();
                  router.replace('/');
                } catch (cause) {
                  setNotice({
                    tone: 'danger',
                    text: cause instanceof ApiError
                      ? cause.message
                      : 'Account data could not all be removed. Your account is still active; please try again.',
                  });
                } finally {
                  setDeleting(false);
                }
              }}
            >
              Delete permanently
            </Button>
          </>
        }
      />
    </div>
  );
}

export function ProfileSettings() {
  return <ProfileView />;
}
