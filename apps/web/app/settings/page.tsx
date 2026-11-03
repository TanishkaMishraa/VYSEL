import type { Metadata } from 'next';
import { AppShell } from '@/components/app/AppShell';
import { ProfileSettings } from '@/components/app/ProfileSettings';
import { RequireAuth } from '@/components/auth/guards';

export const metadata: Metadata = {
  title: 'Settings',
  robots: { index: false, follow: false },
};

export default function SettingsPage() {
  return (
    <RequireAuth>
      <AppShell>
        <ProfileSettings />
      </AppShell>
    </RequireAuth>
  );
}
