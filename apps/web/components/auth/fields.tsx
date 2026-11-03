'use client';

import { useEffect, useState, type InputHTMLAttributes } from 'react';
import { Field, Input } from '@vysel/ui';
import { api } from '@/lib/api';

/** Password input with an accessible show/hide toggle. */
export function PasswordField({
  label = 'Password',
  hint,
  error,
  ...input
}: { label?: string; hint?: string; error?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label} hint={hint} error={error}>
      <Input
        {...input}
        type={visible ? 'text' : 'password'}
        endAdornment={
          <button type="button" className="au-reveal" onClick={() => setVisible((v) => !v)} aria-pressed={visible} aria-label={visible ? 'Hide password' : 'Show password'}>
            {visible ? 'Hide' : 'Show'}
          </button>
        }
      />
    </Field>
  );
}

/** "Continue with Google" — rendered only when the API reports Google sign-in is configured. */
export function GoogleButton({ next }: { next?: string }) {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    api<{ google: boolean }>('/auth/providers')
      .then((p) => setEnabled(p.google))
      .catch(() => setEnabled(false));
  }, []);
  if (!enabled) return null;

  const href = `/api/v1/auth/google/start${next ? `?next=${encodeURIComponent(next)}` : ''}`;
  return (
    <>
      {/* Full-page navigation (not fetch): the OAuth flow is a chain of redirects. */}
      <a href={href} className="vy-btn vy-btn--secondary vy-btn--block au-google">
        <span className="vy-btn__label">
          {/* Official multi-colour "G" — required by Google's sign-in branding guidelines. */}
          <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
          </svg>
          Continue with Google
        </span>
      </a>
      <div className="au-divider" role="separator">
        <span>or</span>
      </div>
    </>
  );
}
