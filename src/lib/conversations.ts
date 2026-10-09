/* Conversation REST client (STEP 2/4 endpoints, STEP 6 fields).

   Reuses the shared `request` helper so authentication, the CSRF header,
   single-flight token refresh and error normalisation all behave identically
   to every other call in the app. Only the streaming transport is different,
   and that lives in `@/lib/chat`. */

import { request } from '@/lib/api';

/* Wire shapes, mirroring backend/app/schemas/conversation.py. Timestamps the UI
   does arithmetic on arrive as epoch milliseconds, not ISO strings. */

export interface MessageWire {
  id: string;
  conversationId: string;
  position: number;
  role: 'user' | 'assistant';
  mode: string;
  blocks: { kind: string; body?: string }[];
  reasoning?: string | null;
  traces?: unknown[] | null;
  voice: boolean;
  tokens?: number | null;
  createdAt: number;
  status?: 'streaming' | 'completed' | 'failed' | 'cancelled';
  model?: string | null;
  provider?: string | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  totalTokens?: number | null;
  latencyMs?: number | null;
  errorCode?: string | null;
}

export interface ConversationWire {
  id: string;
  title: string;
  preview: string;
  mode: string;
  project?: string | null;
  pinned?: boolean;
  archived?: boolean;
  messageCount: number;
  updatedAt: number;
  lastMessageAt?: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TurnResultWire {
  userMessage: MessageWire;
  assistantMessage: MessageWire;
  conversation: ConversationWire;
}

export interface ListConversationsQuery {
  limit?: number;
  offset?: number;
  search?: string;
  modeId?: string;
  projectId?: string;
  pinned?: boolean;
  includeArchived?: boolean;
}

export const conversationApi = {
  list(query: ListConversationsQuery = {}, signal?: AbortSignal): Promise<Page<ConversationWire>> {
    return request<Page<ConversationWire>>('/conversations', {
      query: { ...query },
      signal,
    });
  },

  get(id: string, signal?: AbortSignal): Promise<ConversationWire> {
    return request<ConversationWire>(`/conversations/${encodeURIComponent(id)}`, { signal });
  },

  create(
    input: { title?: string; mode?: string; project?: string },
    signal?: AbortSignal,
  ): Promise<ConversationWire> {
    return request<ConversationWire>('/conversations', { method: 'POST', body: input, signal });
  },

  update(
    id: string,
    patch: { title?: string; mode?: string; pinned?: boolean; archived?: boolean },
    signal?: AbortSignal,
  ): Promise<ConversationWire> {
    return request<ConversationWire>(`/conversations/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: patch,
      signal,
    });
  },

  remove(id: string, signal?: AbortSignal): Promise<void> {
    return request<void>(`/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      signal,
    });
  },

  messages(
    id: string,
    query: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<Page<MessageWire>> {
    return request<Page<MessageWire>>(`/conversations/${encodeURIComponent(id)}/messages`, {
      query: { ...query },
      signal,
    });
  },

  /** Non-streaming send. Used as the fallback when streaming is unavailable. */
  send(
    id: string,
    body: { body: string; mode?: string; voice?: boolean; idempotencyKey?: string },
    signal?: AbortSignal,
  ): Promise<TurnResultWire> {
    return request<TurnResultWire>(`/conversations/${encodeURIComponent(id)}/messages`, {
      method: 'POST',
      body,
      signal,
    });
  },
};
