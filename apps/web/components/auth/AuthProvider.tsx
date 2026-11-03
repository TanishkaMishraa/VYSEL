'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, api } from '@/lib/api';
import type { Preferences } from '@/lib/preferences';

export interface Profile {
  id: string;
  email: string;
  display_name: string;
  email_verified: boolean;
  has_password: boolean;
  auth_providers: string[];
  preferences: Preferences;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
}

interface AuthSession {
  access_token: string;
  expires_in: number;
  user: Profile;
}

export interface ProfileUpdate {
  display_name?: string;
  preferences?: Partial<Preferences>;
  onboarding_completed?: boolean;
}

interface AuthContextValue {
  status: 'loading' | 'authenticated' | 'anonymous';
  user: Profile | null;
  login: (email: string, password: string) => Promise<Profile>;
  register: (email: string, password: string, displayName: string) => Promise<Profile>;
  logout: () => Promise<void>;
  /** Re-establish a session from the refresh cookie (e.g. after Google sign-in). */
  restore: () => Promise<Profile | null>;
  updateProfile: (patch: ProfileUpdate) => Promise<Profile>;
  deleteAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// One refresh at a time across the whole app: the refresh token is single-use, so
// parallel refreshes (React StrictMode, several 401s at once) would race each other.
let refreshInFlight: Promise<AuthSession | null> | null = null;

function refreshSession(): Promise<AuthSession | null> {
  refreshInFlight ??= (async () => {
    try {
      return await api<AuthSession>('/auth/refresh', { method: 'POST' });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // Another tab may have just rotated the cookie; one retry picks up the new token.
        await new Promise((r) => setTimeout(r, 400));
        return await api<AuthSession>('/auth/refresh', { method: 'POST' }).catch(() => null);
      }
      return null;
    } finally {
      setTimeout(() => (refreshInFlight = null), 0);
    }
  })();
  return refreshInFlight;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthContextValue['status']>('loading');
  const [user, setUser] = useState<Profile | null>(null);
  // Access token lives in memory only — never localStorage — so XSS can't lift a long-lived credential.
  const token = useRef<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout>>();

  const apply = useCallback((session: AuthSession | null) => {
    clearTimeout(refreshTimer.current);
    token.current = session?.access_token ?? null;
    setUser(session?.user ?? null);
    setStatus(session ? 'authenticated' : 'anonymous');
    if (session) {
      // Renew a minute before expiry so requests rarely hit a 401.
      refreshTimer.current = setTimeout(() => refreshSession().then(apply), Math.max(session.expires_in - 60, 30) * 1000);
    }
    return session?.user ?? null;
  }, []);

  const restore = useCallback(() => refreshSession().then(apply), [apply]);

  useEffect(() => {
    restore();
    return () => clearTimeout(refreshTimer.current);
  }, [restore]);

  /** Authenticated request; on 401 refreshes once and retries. */
  const authed = useCallback(
    async <T,>(path: string, init: Parameters<typeof api>[1] = {}): Promise<T> => {
      try {
        return await api<T>(path, { ...init, token: token.current });
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 401) throw e;
        const session = await refreshSession();
        apply(session);
        if (!session) throw e;
        return api<T>(path, { ...init, token: session.access_token });
      }
    },
    [apply],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      restore,
      login: async (email, password) => apply(await api<AuthSession>('/auth/login', { method: 'POST', json: { email, password } }))!,
      register: async (email, password, display_name) =>
        apply(await api<AuthSession>('/auth/register', { method: 'POST', json: { email, password, display_name } }))!,
      logout: async () => {
        await api('/auth/logout', { method: 'POST' }).catch(() => undefined);
        apply(null);
      },
      updateProfile: async (patch) => {
        const profile = await authed<Profile>('/me', { method: 'PATCH', json: patch });
        setUser(profile);
        return profile;
      },
      deleteAccount: async () => {
        await authed('/me', { method: 'DELETE' });
        apply(null);
      },
    }),
    [status, user, restore, apply, authed],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
