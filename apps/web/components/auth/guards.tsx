'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';
import { Spinner } from '@vysel/ui';
import { useAuth } from './AuthProvider';

function FullPageSpinner() {
  return (
    <div className="au-loading">
      <Spinner size="lg" label="Loading your account" />
    </div>
  );
}

/** Renders children only for signed-in users; otherwise redirects to /login?next=… */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (status === 'anonymous') router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);
  return status === 'authenticated' ? <>{children}</> : <FullPageSpinner />;
}

/** For login/sign-up pages: signed-in users skip straight to their next step. */
export function GuestOnly({ children, next }: { children: ReactNode; next?: string }) {
  const { status, user } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === 'authenticated' && user) router.replace(next ?? (user.onboarding_completed ? '/dashboard' : '/onboarding'));
  }, [status, user, router, next]);
  return status === 'anonymous' ? <>{children}</> : <FullPageSpinner />;
}
