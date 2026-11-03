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

const GOOGLE_ERRORS: Record<string, string> = {
  google_cancelled: 'Google sign-in was cancelled.',
  google_failed: 'Google sign-in didn’t complete. Please try again.',
  google_unverified: 'Your Google email isn’t verified, so we can’t use it to sign you in.',
  google_unavailable: 'Google sign-in isn’t available right now.',
};

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(GOOGLE_ERRORS[params.get('error') ?? ''] ?? null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const user = await login(email, password);
      router.replace(safeNext(next, user.onboarding_completed ? '/dashboard' : '/onboarding'));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
      setLoading(false);
    }
  }

  return (
    <GuestOnly next={next ? safeNext(next) : undefined}>
      <AuthShell
        eyebrow="Welcome back"
        title="Sign in to VYSEL"
        footer={
          <>
            New to VYSEL? <Link href={`/signup${next ? `?next=${encodeURIComponent(next)}` : ''}`}>Create an account</Link>
          </>
        }
      >
        <GoogleButton next={next ?? undefined} />
        <form className="au-fields" onSubmit={onSubmit} noValidate>
          {error && (
            <Alert tone="danger" title="Couldn’t sign you in">
              {error}
            </Alert>
          )}
          <Field label="Email">
            <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <PasswordField autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <Link href="/forgot-password" className="au-inline-link">
            Forgot your password?
          </Link>
          <Button type="submit" size="lg" block loading={loading}>
            Sign in
          </Button>
        </form>
      </AuthShell>
    </GuestOnly>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
