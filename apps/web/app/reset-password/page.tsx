'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useState, type FormEvent } from 'react';
import { Alert, Button, StateMessage, buttonClassName } from '@vysel/ui';
import { AuthShell } from '@/components/auth/AuthShell';
import { PasswordField } from '@/components/auth/fields';
import { ApiError, api } from '@/lib/api';

function ResetForm() {
  const token = useSearchParams().get('token');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <StateMessage
        kind="error"
        title="This link is incomplete"
        description="Open the link from your email again, or request a new one."
        actions={
          <Link href="/forgot-password" className={buttonClassName()}>
            <span className="vy-btn__label">Request a new link</span>
          </Link>
        }
      />
    );
  }

  if (done) {
    return (
      <StateMessage
        kind="success"
        title="Password updated"
        description="For your security, you’ve been signed out on all devices. Sign in with your new password."
        actions={
          <Link href="/login" className={buttonClassName()}>
            <span className="vy-btn__label">Sign in</span>
          </Link>
        }
      />
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 10) return setError(new ApiError(422, 'VALIDATION_ERROR', '', [{ field: 'password', message: 'Use at least 10 characters.' }]));
    if (password !== confirm) return setError(new ApiError(422, 'VALIDATION_ERROR', '', [{ field: 'confirm', message: 'Passwords don’t match.' }]));
    setLoading(true);
    try {
      await api('/auth/password/reset', { method: 'POST', json: { token, password } });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'INTERNAL_ERROR', 'Something went wrong. Please try again.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="au-fields" onSubmit={onSubmit} noValidate>
      {error && !error.errors.length && (
        <Alert tone="danger" title={error.code === 'RESET_TOKEN_INVALID' ? 'This link has expired' : undefined}>
          {error.message} {error.code === 'RESET_TOKEN_INVALID' && <Link href="/forgot-password">Send a new link</Link>}
        </Alert>
      )}
      <PasswordField
        label="New password"
        autoComplete="new-password"
        hint="At least 10 characters."
        error={error?.fieldError('password')}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <PasswordField label="Confirm new password" autoComplete="new-password" error={error?.fieldError('confirm')} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <Button type="submit" size="lg" block loading={loading}>
        Update password
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell eyebrow="Account help" title="Choose a new password" footer={<Link href="/login">Back to sign in</Link>}>
      <Suspense>
        <ResetForm />
      </Suspense>
    </AuthShell>
  );
}
