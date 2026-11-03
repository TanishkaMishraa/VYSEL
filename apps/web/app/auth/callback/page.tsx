'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef } from 'react';
import { Spinner } from '@vysel/ui';
import { useAuth } from '@/components/auth/AuthProvider';
import { safeNext } from '@/lib/api';

/** Landing point after Google sign-in: the API already set the refresh cookie. */
function Callback() {
  const { restore } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get('next');
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    restore().then((user) => {
      if (!user) return router.replace('/login?error=google_failed');
      router.replace(user.onboarding_completed ? safeNext(next, '/dashboard') : '/onboarding');
    });
  }, [restore, router, next]);

  return (
    <div className="au-loading">
      <Spinner size="lg" label="Signing you in" />
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <Callback />
    </Suspense>
  );
}
