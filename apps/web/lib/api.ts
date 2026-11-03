/**
 * Minimal client for the VYSEL API, reached same-origin through the Next.js proxy
 * (/api/v1 → FastAPI). Non-2xx responses are RFC 9457 problem+json → ApiError.
 */

export interface FieldError {
  field: string;
  message: string;
  code?: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public errors: FieldError[] = [],
  ) {
    super(message);
  }

  /** First message for a given field, for inline form errors. */
  fieldError(field: string): string | undefined {
    return this.errors.find((e) => e.field === field)?.message;
  }
}

export async function api<T>(path: string, init: RequestInit & { token?: string | null; json?: unknown } = {}): Promise<T> {
  const { token, json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      credentials: 'same-origin',
      ...rest,
      headers: {
        Accept: 'application/json',
        ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Can’t reach VYSEL right now. Check your connection and try again.');
  }

  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = body?.detail ?? body?.title ?? 'Something went wrong. Please try again.';
    throw new ApiError(res.status, body?.code ?? 'INTERNAL_ERROR', message, body?.errors ?? []);
  }
  return body as T;
}

/** Same rule as the API: only same-site relative paths, never `//host` (open redirect). */
export function safeNext(next: string | null | undefined, fallback = '/profile'): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') ? next : fallback;
}
