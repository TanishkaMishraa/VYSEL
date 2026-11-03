'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState, type FormEvent } from 'react';
import { Alert, Button, Field, Input } from '@vysel/ui';
import { useAuth } from '@/components/auth/AuthProvider';
import { AuthShell } from '@/components/auth/AuthShell';
import { GoogleButton, PasswordField } from '@/components/auth/fields';
import { GuestOnly } from '@/components/auth/guards';
import { ApiError, safeNext } from '@/lib/api';

function SignupForm() {
  const { register } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get('next');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.password.length < 10) {
      setError(new ApiError(422, 'VALIDATION_ERROR', 'Check the highlighted field.', [{ field: 'password', message: 'Use at least 10 characters.' }]));
      return;
    }
    setLoading(true);
    try {
      await register(form.email, form.password, form.name);
      router.replace(safeNext(next, '/onboarding'));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'INTERNAL_ERROR', 'Something went wrong. Please try again.'));
      setLoading(false);
    }
  }

  const fieldError = (f: string) => error?.fieldError(f);
  const showBanner = error && !error.errors.length;

  return (
    <GuestOnly next={next ? safeNext(next) : undefined}>
      <AuthShell
        eyebrow="Create your account"
        title="Meet your Style DNA"
        lead="A few details, then a short questionnaire about your style goals."
        footer={
          <>
            Already have an account? <Link href={`/login${next ? `?next=${encodeURIComponent(next)}` : ''}`}>Sign in</Link>
          </>
        }
      >
        <GoogleButton next={next ?? '/onboarding'} />
        <form className="au-fields" onSubmit={onSubmit} noValidate>
          {showBanner && (
            <Alert tone="danger" title={error.code === 'EMAIL_TAKEN' ? 'That email already has an account' : 'Couldn’t create your account'}>
              {error.code === 'EMAIL_TAKEN' ? (
                <>
                  Try <Link href="/login">signing in</Link> or <Link href="/forgot-password">resetting your password</Link>.
                </>
              ) : (
                error.message
              )}
            </Alert>
          )}
          <Field label="Your name" error={fieldError('display_name')}>
            <Input autoComplete="given-name" required maxLength={50} value={form.name} onChange={set('name')} />
          </Field>
          <Field label="Email" error={fieldError('email')}>
            <Input type="email" autoComplete="email" required value={form.email} onChange={set('email')} />
          </Field>
          <PasswordField
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={128}
            hint="At least 10 characters. A short phrase works well."
            error={fieldError('password')}
            value={form.password}
            onChange={set('password')}
          />
          <Button type="submit" size="lg" block loading={loading}>
            Create account
          </Button>
          <p className="vy-caption">We never share your details. Your selfies are deleted after analysis by default.</p>
        </form>
      </AuthShell>
    </GuestOnly>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
