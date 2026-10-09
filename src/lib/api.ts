/* The single seam between the SPA and the FastAPI backend.

   Design decisions worth knowing before editing:

   * Credentials are HttpOnly cookies, so this module never sees or stores a
     token. There is deliberately nothing here that touches localStorage or
     sessionStorage — an XSS bug cannot read a session it cannot reach.
   * The CSRF cookie is readable by design. We echo it back in `X-CSRF-Token`
     on unsafe methods; the backend compares the two with a constant-time
     check.
   * A 401 triggers exactly one refresh-and-retry. The retry is single-flight
     so a burst of concurrent 401s cannot stampede the refresh endpoint and
     invalidate its own rotating token. */

import type {
  AdminAIUsage,
  AdminEventFeed,
  AdminPage,
  AdminSystemHealth,
  AdminUsage,
  AdminUser,
  AuthSession,
  AuthState,
  AuthUser,
  LoginInput,
  Preferences,
  RegisterInput,
} from '@/lib/authTypes';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
export const API_PREFIX = '/api/v1';

/* Read by JS on purpose; the backend sets it non-HttpOnly. */
const CSRF_COOKIE = 'aurelis_csrf';
const CSRF_HEADER = 'X-CSRF-Token';

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/* ── Error shape ──────────────────────────────────────────────────── */

export type ApiErrorKind =
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'validation'
  | 'rate_limited'
  | 'network'
  | 'server'
  | 'unknown';

/**
 * A single error type for every failure path, carrying a message that is
 * always safe to render. The backend already avoids leaking internals, and
 * this class never surfaces a raw response body or stack trace.
 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly code: string;
  readonly retryAfterSeconds: number | null;
  /** Field-level copy from a validation failure, when the server sent any. */
  readonly detail: string | null;
  /** The request field that detail refers to, e.g. `password`. */
  readonly field: string | null;

  constructor(
    message: string,
    options: {
      kind: ApiErrorKind;
      status?: number;
      code?: string;
      retryAfterSeconds?: number | null;
      detail?: string;
      field?: string;
    },
  ) {
    super(message);
    this.name = 'ApiError';
    this.kind = options.kind;
    this.status = options.status ?? 0;
    this.code = options.code ?? options.kind;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.detail = options.detail ?? null;
    this.field = options.field ?? null;
  }

  /** The most useful safe thing to show: field copy beats the envelope. */
  get displayMessage(): string {
    return this.detail ?? this.message;
  }

  get isAuthFailure(): boolean {
    return this.kind === 'unauthorized';
  }

  get isPermissionFailure(): boolean {
    return this.kind === 'forbidden';
  }
}

export const NETWORK_ERROR_MESSAGE = 'Unable to connect to the server. Please try again.';
export const GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.';
export const INVALID_CREDENTIALS_MESSAGE = 'Invalid email or password.';
export const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.';
export const FORBIDDEN_MESSAGE = 'You do not have permission to access this resource.';

function kindForStatus(status: number): ApiErrorKind {
  switch (status) {
    case 401:
      return 'unauthorized';
    case 403:
      return 'forbidden';
    case 404:
      return 'not_found';
    case 409:
      return 'conflict';
    case 422:
      return 'validation';
    case 429:
      return 'rate_limited';
    default:
      return status >= 500 ? 'server' : 'unknown';
  }
}

/** Fallback copy per status, used when the body carries no usable message. */
function fallbackMessage(kind: ApiErrorKind): string {
  switch (kind) {
    case 'unauthorized':
      return SESSION_EXPIRED_MESSAGE;
    case 'forbidden':
      return FORBIDDEN_MESSAGE;
    case 'not_found':
      return 'That resource could not be found.';
    case 'conflict':
      return 'That request conflicts with an existing record.';
    case 'validation':
      return 'Please check the details you entered.';
    case 'rate_limited':
      return 'Too many attempts. Please wait a moment and try again.';
    case 'network':
      return NETWORK_ERROR_MESSAGE;
    case 'server':
      return 'The server is temporarily unavailable. Please try again.';
    default:
      return GENERIC_ERROR_MESSAGE;
  }
}

/** Pull the backend's `{error:{code,message}}` envelope, defensively. */
function readErrorEnvelope(body: unknown): {
  code?: string;
  message?: string;
  detail?: string;
  field?: string;
} {
  if (!body || typeof body !== 'object') return {};
  const envelope = (body as { error?: unknown }).error;
  if (!envelope || typeof envelope !== 'object') return {};
  const { code, message, details } = envelope as {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  const first = firstDetail(details);
  return {
    code: typeof code === 'string' ? code : undefined,
    message: typeof message === 'string' && message.trim() ? message : undefined,
    detail: first?.message,
    field: first?.field,
  };
}

/* Validation failures carry the useful copy per field (`Password is too
   common`) while `message` stays generic on purpose. Surface the first field
   message so the form can explain itself; it is server-authored text that has
   already been screened for internal detail. */
function firstDetail(details: unknown): { message: string; field?: string } | undefined {
  if (!Array.isArray(details)) return undefined;
  for (const entry of details) {
    if (!entry || typeof entry !== 'object') continue;
    const { msg, loc } = entry as { msg?: unknown; loc?: unknown };
    if (typeof msg !== 'string' || !msg.trim()) continue;
    /* `loc` is like ["body", "password"]; the last string segment names the
       offending field. */
    const field =
      Array.isArray(loc) && typeof loc[loc.length - 1] === 'string'
        ? (loc[loc.length - 1] as string)
        : undefined;
    /* Pydantic prefixes raised `ValueError`s with the validator name. */
    return { message: msg.replace(/^Value error,\s*/i, '').trim(), field };
  }
  return undefined;
}

function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${CSRF_COOKIE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

/* ── Session-expiry notification ──────────────────────────────────── */

/* The refresh attempt lives here rather than in AuthContext so a 401 from any
   caller — including background polling — benefits from it. When a refresh
   ultimately fails, this listener lets AuthContext flip to the signed-out
   state without the API layer importing React. */
type SessionExpiredListener = () => void;
const sessionExpiredListeners = new Set<SessionExpiredListener>();

export function onSessionExpired(listener: SessionExpiredListener): () => void {
  sessionExpiredListeners.add(listener);
  return () => sessionExpiredListeners.delete(listener);
}

function announceSessionExpired(): void {
  for (const listener of sessionExpiredListeners) listener();
}

/* ── Request plumbing ─────────────────────────────────────────────── */

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  /* Internal: marks a request that is itself a refresh, so a 401 from it does
     not recurse into another refresh. */
  skipRefresh?: boolean;
  query?: Record<string, string | number | boolean | undefined | null>;
}

export type { RequestOptions };

/* Single-flight refresh. Concurrent 401s await the same promise instead of
   each starting a rotation, which would revoke the token the others hold. */
let refreshInFlight: Promise<boolean> | null = null;

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `${API_BASE}${API_PREFIX}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* A non-JSON body (proxy error page, empty 502) is not our concern. */
  }

  const kind = kindForStatus(response.status);
  const { code, message, detail, field } = readErrorEnvelope(body);

  const retryHeader = response.headers.get('Retry-After');
  const retryAfter = retryHeader ? Number.parseInt(retryHeader, 10) : NaN;

  return new ApiError(message ?? fallbackMessage(kind), {
    kind,
    status: response.status,
    code,
    retryAfterSeconds: Number.isFinite(retryAfter) ? retryAfter : null,
    detail,
    field,
  });
}

async function performRefresh(): Promise<boolean> {
  try {
    const response = await fetch(buildUrl('/auth/refresh'), {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...csrfHeader(),
      },
    });
    return response.ok;
  } catch {
    return false;
  }
}

export function csrfHeader(): Record<string, string> {
  const token = readCsrfCookie();
  return token ? { [CSRF_HEADER]: token } : {};
}

export async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (UNSAFE_METHODS.has(method)) Object.assign(headers, csrfHeader());

    return fetch(buildUrl(path, options.query), {
      method,
      headers,
      credentials: 'include',
      signal: options.signal,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  };

  let response: Response;
  try {
    response = await send();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(NETWORK_ERROR_MESSAGE, { kind: 'network', status: 0 });
  }

  /* One transparent refresh-and-retry. Only for a genuine session expiry on a
     non-refresh request; a 403 is a real authorization denial and must not be
     retried. */
  if (response.status === 401 && !options.skipRefresh) {
    const refreshed = await refreshSession();
    if (!refreshed) {
      announceSessionExpired();
      throw await toApiError(response);
    }
    try {
      response = await send();
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error;
      throw new ApiError(NETWORK_ERROR_MESSAGE, { kind: 'network', status: 0 });
    }
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;

  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(GENERIC_ERROR_MESSAGE, { kind: 'server', status: response.status });
  }
}

/* ── Auth endpoints ───────────────────────────────────────────────── */

export const authApi = {
  register(input: RegisterInput): Promise<AuthState> {
    return request<AuthState>('/auth/register', {
      method: 'POST',
      body: {
        fullName: input.fullName,
        email: input.email,
        password: input.password,
        confirmPassword: input.confirmPassword,
      },
      /* A failed register cannot be fixed by refreshing; skip the round trip. */
      skipRefresh: true,
    });
  },

  login(input: LoginInput): Promise<AuthState> {
    return request<AuthState>('/auth/login', {
      method: 'POST',
      body: { email: input.email, password: input.password },
      skipRefresh: true,
    });
  },

  logout(): Promise<{ status: string; message: string }> {
    return request('/auth/logout', { method: 'POST', skipRefresh: true });
  },

  me(signal?: AbortSignal): Promise<AuthState> {
    return request<AuthState>('/auth/me', { signal, skipRefresh: true });
  },

  changePassword(input: {
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
  }): Promise<{ status: string; message: string }> {
    return request('/auth/change-password', { method: 'POST', body: input });
  },

  forgotPassword(email: string): Promise<{ status: string; message: string; delivery: string }> {
    return request('/auth/forgot-password', {
      method: 'POST',
      body: { email },
      skipRefresh: true,
    });
  },

  resetPassword(input: {
    token: string;
    password: string;
    confirmPassword: string;
  }): Promise<{ status: string; message: string }> {
    return request('/auth/reset-password', {
      method: 'POST',
      body: input,
      skipRefresh: true,
    });
  },

  sessions(): Promise<AuthSession[]> {
    return request<AuthSession[]>('/auth/sessions');
  },

  revokeAllSessions(): Promise<{ status: string; message: string }> {
    return request('/auth/sessions', { method: 'DELETE' });
  },

  updateProfile(patch: {
    fullName?: string;
    avatarUrl?: string | null;
  }): Promise<AuthUser> {
    return request<AuthUser>('/auth/profile', { method: 'PATCH', body: patch });
  },

  updatePreferences(patch: Partial<Preferences>): Promise<Preferences> {
    return request<Preferences>('/auth/preferences', { method: 'PATCH', body: patch });
  },
};

/* ── Admin endpoints ──────────────────────────────────────────────── */

export const adminApi = {
  users(params: {
    search?: string;
    role?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<AdminPage<AdminUser>> {
    return request<AdminPage<AdminUser>>('/admin/users', { query: params });
  },

  user(id: string): Promise<AdminUser> {
    return request<AdminUser>(`/admin/users/${encodeURIComponent(id)}`);
  },

  updateUser(id: string, patch: { role?: string; isActive?: boolean }): Promise<AdminUser> {
    return request<AdminUser>(`/admin/users/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: patch,
    });
  },

  usage(): Promise<AdminUsage> {
    return request<AdminUsage>('/admin/usage');
  },

  aiUsage(windowDays = 30): Promise<AdminAIUsage> {
    return request<AdminAIUsage>('/admin/ai-usage', { query: { windowDays } });
  },

  events(params: { eventType?: string; outcome?: string; limit?: number; offset?: number } = {}) {
    return request<AdminEventFeed>('/admin/events', { query: params });
  },

  systemHealth(): Promise<AdminSystemHealth> {
    return request<AdminSystemHealth>('/admin/system-health');
  },

  userSessions(id: string): Promise<AuthSession[]> {
    return request<AuthSession[]>(`/admin/users/${encodeURIComponent(id)}/sessions`);
  },

  revokeUserSessions(id: string): Promise<{ status: string; message: string }> {
    return request(`/admin/users/${encodeURIComponent(id)}/sessions/revoke`, {
      method: 'POST',
    });
  },
};

/** Human-readable text for any thrown value, safe to render directly. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.displayMessage;
  return GENERIC_ERROR_MESSAGE;
}
