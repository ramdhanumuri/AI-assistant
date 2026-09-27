/* Authentication and authorization wire types.

   Mirrors `backend/app/schemas/auth.py`. The backend serialises camelCase
   (`alias_generator=to_camel`), so these names match the wire exactly — no
   snake_case translation layer is needed here. */

export type Role = 'user' | 'admin';

export interface AuthUser {
  id: string;
  fullName: string;
  email: string;
  role: Role;
  isActive: boolean;
  avatarUrl: string | null;
  emailVerified: boolean;
  createdAt: number;
}

export interface Preferences {
  ambientLight: boolean;
  particles: boolean;
  reduceMotion: boolean;
  streaming: boolean;
  memory: boolean;
  citations: boolean;
  soundscape: boolean;
  density: 'comfortable' | 'compact';
}

export interface AuthState {
  user: AuthUser;
  preferences: Preferences;
  /* Epoch millis. Lets the client refresh proactively instead of waiting for a
     401 on the next write. */
  accessTokenExpiresAt: number;
}

export interface AuthSession {
  id: string;
  createdAt: number;
  expiresAt: number;
  lastUsedAt: number | null;
  userAgent: string | null;
  current: boolean;
}

export interface RegisterInput {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

/* ── Admin surface ────────────────────────────────────────────────── */

export interface AdminUser extends AuthUser {
  lastLoginAt: number | null;
  failedLoginCount: number;
  lockedUntil: number | null;
  activeSessions: number;
  conversationCount: number;
}

export interface AdminPage<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminUsageBucket {
  label: string;
  value: number;
  secondary: number;
}

export interface AdminUsage {
  totalUsers: number;
  activeUsers: number;
  adminUsers: number;
  /* `to_camel` turns `new_users_7d` into `newUsers7D` and `..._24h` into
     `...24H` — the digit keeps the trailing letter, it is not lowercased. */
  newUsers7D: number;
  totalConversations: number;
  totalMessages: number;
  activeSessions: number;
  sessionsCreated24H: number;
  authEvents24H: number;
  failedLogins24H: number;
  usage: AdminUsageBucket[];
}

export interface AdminEvent {
  id: number;
  eventType: string;
  outcome: 'success' | 'failure' | 'denied' | string;
  userId: string | null;
  emailHash: string | null;
  ipHash: string | null;
  detail: string | null;
  occurredAt: number;
}

export interface AdminEventFeed {
  items: AdminEvent[];
  total: number;
  limit: number;
  offset: number;
  countsByType: Record<string, number>;
}

export interface AdminSystemHealth {
  status: string;
  environment: string;
  version: string;
  database: string;
  databaseDialect: string;
  supabase: string;
  aiProvider: string;
  authSecretConfigured: boolean;
  cookieSecure: boolean;
  cookieSamesite: string;
  accessTokenMinutes: number;
  refreshTokenDays: number;
  passwordHashing: string;
  mailConfigured: boolean;
  checkedAt: number;
}
