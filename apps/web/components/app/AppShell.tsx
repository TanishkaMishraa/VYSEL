'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { Button, Wordmark } from '@vysel/ui';
import { useAuth } from '@/components/auth/AuthProvider';

/** Chrome for signed-in pages: wordmark, account name, sign out. */
export function AppShell({ children, narrow }: { children: ReactNode; narrow?: boolean }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  return (
    <>
      <header className="vy-nav">
        <div className="vy-container vy-nav__inner">
          <Link href="/" className="vy-nav__brand" aria-label="VYSEL home">
            <Wordmark title={null} />
          </Link>
          <nav className="app-nav" aria-label="Application">
            {[
              { href: '/dashboard', label: 'Dashboard' },
              { href: '/scan', label: 'New scan' },
              { href: '/try-on', label: 'Try-on' },
              { href: '/settings', label: 'Settings' },
            ].map((item) => (
              <Link key={item.href} href={item.href} className="vy-nav__link" aria-current={pathname === item.href ? 'page' : undefined}>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="app-account">
            {user && (
              <Link href="/settings" className="vy-nav__link app-account__name">
                {user.display_name}
              </Link>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                await logout();
                router.replace('/');
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className={`vy-container ${narrow ? 'vy-container--narrow' : ''} app-main`}>
        {children}
      </main>
    </>
  );
}
