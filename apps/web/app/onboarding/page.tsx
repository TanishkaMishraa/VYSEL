'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Alert, Badge, Button, Progress, StateMessage, buttonClassName } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { useAuth } from '@/components/auth/AuthProvider';
import { ChoiceGrid } from '@/components/auth/ChoiceGrid';
import { RequireAuth } from '@/components/auth/guards';
import { ApiError } from '@/lib/api';
import {
  BUDGETS,
  OCCASIONS,
  STYLE_GOALS,
  STYLES,
  categoriesFor,
  labelOf,
  type Budget,
  type Occasion,
  type StyleGoal,
  type StylePreference,
} from '@/lib/preferences';

const STEPS = ['Your goals', 'Occasions', 'Budget & style', 'Review'] as const;

function Questionnaire() {
  const { user, updateProfile } = useAuth();
  const prefs = user!.preferences;
  const [step, setStep] = useState(0);
  const [goals, setGoals] = useState<StyleGoal[]>(prefs.style_goals);
  const [occasions, setOccasions] = useState<Occasion[]>(prefs.occasions);
  const [budget, setBudget] = useState<Budget | null>(prefs.budget);
  const [style, setStyle] = useState<StylePreference | null>(prefs.style);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);

  // Move focus to the new step's heading so keyboard and screen-reader users land in context.
  useEffect(() => {
    if (first.current) return void (first.current = false);
    heading.current?.focus();
  }, [step, done]);

  const answers = { style_goals: goals, occasions, budget, style, categories: categoriesFor(goals) };
  const missing = [
    !goals.length && 'Pick at least one goal.',
    !occasions.length && 'Pick at least one occasion.',
    !budget && 'Choose a budget.',
  ][step];

  async function save(complete: boolean) {
    setError(null);
    setSaving(true);
    try {
      // Saved at every step, so answers survive a closed tab.
      await updateProfile({ preferences: answers, ...(complete ? { onboarding_completed: true } : {}) });
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Couldn’t save your answers. Please try again.');
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function next() {
    if (missing) return setError(missing);
    if (step === STEPS.length - 1) {
      if (await save(true)) setDone(true);
    } else if (await save(false)) {
      setStep(step + 1);
    }
  }

  if (done) {
    return (
      <StateMessage
        kind="success"
        title="Your style profile is ready"
        description="We’ll use these answers to tailor your Style DNA. You can change them any time from your profile."
        actions={
          <Link href="/dashboard" className={buttonClassName()}>
            <span className="vy-btn__label">Go to your dashboard</span>
          </Link>
        }
      />
    );
  }

  return (
    <div className="ob">
      <div className="ob__progress">
        <div className="flex items-baseline justify-between gap-4">
          <p className="vy-overline">
            Step {step + 1} of {STEPS.length} · {STEPS[step]}
          </p>
          <span className="vy-caption">About a minute</span>
        </div>
        <Progress value={((step + 1) / STEPS.length) * 100} label={`Questionnaire progress: step ${step + 1} of ${STEPS.length}`} />
      </div>

      <section className="ob__step" aria-labelledby="ob-title" key={step}>
        {step === 0 && (
          <>
            <h1 className="vy-h3" id="ob-title" ref={heading} tabIndex={-1}>
              What would you like VYSEL to help with?
            </h1>
            <ChoiceGrid legend="Style goals" hint="Choose all that apply." name="goals" multiple options={STYLE_GOALS} value={goals} onChange={setGoals} />
          </>
        )}
        {step === 1 && (
          <>
            <h1 className="vy-h3" id="ob-title" ref={heading} tabIndex={-1}>
              Where do you want to look your best?
            </h1>
            <ChoiceGrid legend="Preferred occasions" hint="Choose all that apply." name="occasions" multiple options={OCCASIONS} value={occasions} onChange={setOccasions} />
          </>
        )}
        {step === 2 && (
          <>
            <h1 className="vy-h3" id="ob-title" ref={heading} tabIndex={-1}>
              What fits your budget and taste?
            </h1>
            <ChoiceGrid legend="Budget" hint="We rank picks within your budget first." name="budget" options={BUDGETS} value={budget} onChange={setBudget} />
            <ChoiceGrid legend="Style (optional)" name="style" options={STYLES} value={style} onChange={setStyle} />
          </>
        )}
        {step === 3 && (
          <>
            <h1 className="vy-h3" id="ob-title" ref={heading} tabIndex={-1}>
              Does this look right?
            </h1>
            <dl className="ob__review">
              {[
                { term: 'Goals', value: goals.map((g) => labelOf(STYLE_GOALS, g)), to: 0 },
                { term: 'Occasions', value: occasions.map((o) => labelOf(OCCASIONS, o)), to: 1 },
                { term: 'Budget', value: [labelOf(BUDGETS, budget)], to: 2 },
                { term: 'Style', value: style ? [labelOf(STYLES, style)] : ['No preference'], to: 2 },
              ].map((row) => (
                <div key={row.term} className="ob__review-row">
                  <dt className="vy-overline">{row.term}</dt>
                  <dd>
                    <span className="flex flex-wrap gap-2">
                      {row.value.map((v) => (
                        <Badge key={v}>{v}</Badge>
                      ))}
                    </span>
                    <button type="button" className="au-inline-link" onClick={() => setStep(row.to)}>
                      Edit<span className="vy-visually-hidden"> {row.term.toLowerCase()}</span>
                    </button>
                  </dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </section>

      {error && <Alert tone="danger">{error}</Alert>}

      <div className="ob__nav">
        {step > 0 ? (
          <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={saving}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={next} loading={saving}>
          {step === STEPS.length - 1 ? 'Save my profile' : 'Continue'}
        </Button>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <AppShell narrow>
        <Questionnaire />
      </AppShell>
    </RequireAuth>
  );
}
