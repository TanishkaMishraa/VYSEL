'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';
import { Alert, Button, Field, Input, StateMessage } from '@vysel/ui';
import { AuthShell } from '@/components/auth/AuthShell';
import { ApiError, api } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api('/auth/password/forgot', { method: 'POST', json: { email } });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Account help"
      title="Reset your password"
      lead={sent ? undefined : 'Enter your email and we’ll send you a link to choose a new password.'}
      footer={<Link href="/login">Back to sign in</Link>}
    >
      {sent ? (
        <StateMessage
          kind="success"
          icon="check"
          title="Check your inbox"
          description={`If an account exists for ${email}, a reset link is on its way. It works once and expires in 30 minutes.`}
        />
      ) : (
        <form className="au-fields" onSubmit={onSubmit} noValidate>
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Email">
            <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Button type="submit" size="lg" block loading={loading}>
            Send reset link
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
