/* The AI chat transport.

   One module owns every call to the STEP 6 AI endpoints, so the streaming
   protocol is described in exactly one place.

   Design decisions worth knowing before editing:

   * Streaming uses `fetch` + a `ReadableStream` reader, not `EventSource`.
     `EventSource` cannot send a POST body, cannot attach the `X-CSRF-Token`
     header, and reconnects on its own — all three are wrong for a
     cookie-authenticated, CSRF-protected, user-cancellable generation.
   * The provider API key never appears here. The browser talks only to our own
     backend; the key lives exclusively in the FastAPI process.
   * A failure after the first byte arrives as an in-band `error` frame, because
     a `200 OK` SSE response has already been sent. Only failures detected
     *before* the stream starts (401/404/429/503) are HTTP status codes, and
     those are mapped onto the same `ApiError` the rest of the app uses. */

import { ApiError, API_BASE, API_PREFIX, csrfHeader, errorMessage, refreshSession } from '@/lib/api';

/* ── Wire types (mirror backend/app/schemas/conversation.py) ──────── */

export interface ChatMessageWire {
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
  status: 'streaming' | 'completed' | 'failed' | 'cancelled';
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

export interface AICapabilities {
  provider: string;
  model: string;
  streamingEnabled: boolean;
  configured: boolean;
  models: { id: string; default: boolean }[];
}

export interface AIUsageSummary {
  totalRequests: number;
  completedRequests: number;
  failedRequests: number;
  cancelledRequests: number;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  averageLatencyMs: number | null;
  estimatedCost: number | null;
  currency: string | null;
  windowDays: number | null;
}

/* ── Stream event handlers ────────────────────────────────────────── */

export interface ChatStreamHandlers {
  /** Fired once, before any text: the persisted user turn and placeholder. */
  onMeta?: (meta: {
    conversationId: string;
    userMessage: ChatMessageWire;
    assistantMessage: ChatMessageWire;
    model: string;
    provider: string;
    replayed: boolean;
  }) => void;
  /** Incremental assistant text. Append, never replace. */
  onDelta: (text: string) => void;
  /** The generation finished successfully; carries the persisted message. */
  onDone?: (message: ChatMessageWire, conversation: ConversationWire) => void;
  /** A terminal failure. `partialText` is what arrived before the failure. */
  onError?: (error: ChatStreamError) => void;
}

export interface ChatStreamError {
  code: string;
  message: string;
  retryable: boolean;
  assistantMessage?: ChatMessageWire | null;
}

/* ── Request plumbing ─────────────────────────────────────────────── */

function streamUrl(conversationId: string): string {
  return `${API_BASE}${API_PREFIX}/ai/conversations/${encodeURIComponent(
    conversationId,
  )}/messages/stream`;
}

/** A stable idempotency key for one logical send. */
export function newIdempotencyKey(): string {
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
  return `send:${random}`;
}

export interface SendMessageInput {
  conversationId: string;
  body: string;
  mode?: string;
  model?: string;
  voice?: boolean;
  idempotencyKey: string;
  signal?: AbortSignal;
}

/**
 * Send a turn and consume the assistant response as it streams.
 *
 * Resolves when the stream reaches a terminal frame. A cancellation (via
 * `signal`) throws a `DOMException` named `AbortError`, exactly like `fetch`,
 * so the caller handles "user stopped it" the same way it handles any abort.
 */
export async function streamChatMessage(
  input: SendMessageInput,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const send = (): Promise<Response> =>
    fetch(streamUrl(input.conversationId), {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        ...csrfHeader(),
      },
      body: JSON.stringify({
        body: input.body,
        mode: input.mode,
        model: input.model,
        voice: input.voice ?? false,
        idempotencyKey: input.idempotencyKey,
      }),
      signal: input.signal,
    });

  let response: Response;
  try {
    response = await send();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('Unable to connect to the server. Please try again.', {
      kind: 'network',
      status: 0,
    });
  }

  /* A single transparent refresh-and-retry, matching the rest of the app. The
     request has not started streaming yet, so retrying is safe. */
  if (response.status === 401) {
    const refreshed = await refreshSession();
    if (!refreshed) throw await streamError(response);
    try {
      response = await send();
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error;
      throw new ApiError('Unable to connect to the server. Please try again.', {
        kind: 'network',
        status: 0,
      });
    }
  }

  if (!response.ok || !response.body) {
    throw await streamError(response);
  }

  await consumeStream(response.body, handlers);
}

/** Read the SSE body and dispatch each frame to the handlers. */
async function consumeStream(
  body: ReadableStream<Uint8Array>,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      // `stream: true` keeps a multi-byte UTF-8 character (Telugu, emoji) that
      // straddles a chunk boundary from being corrupted into replacement
      // characters.
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        dispatchFrame(raw, handlers);
        boundary = buffer.indexOf('\n\n');
      }
    }
    // Flush any trailing frame that arrived without a final blank line.
    if (buffer.trim()) dispatchFrame(buffer, handlers);
  } finally {
    reader.releaseLock();
  }
}

function dispatchFrame(raw: string, handlers: ChatStreamHandlers): void {
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of raw.split('\n')) {
    if (line.startsWith(':')) continue; // heartbeat comment
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join('\n'));
  } catch {
    return; // a malformed frame is dropped rather than crashing the stream
  }

  if (event === 'meta') {
    const meta = data as {
      conversationId: string;
      userMessage: ChatMessageWire;
      assistantMessage: ChatMessageWire;
      model: string;
      provider: string;
      replayed: boolean;
    };
    handlers.onMeta?.(meta);
  } else if (event === 'delta') {
    const delta = data as { text?: string };
    if (delta.text) handlers.onDelta(delta.text);
  } else if (event === 'done') {
    const done = data as {
      assistantMessage: ChatMessageWire;
      conversation: ConversationWire;
    };
    handlers.onDone?.(done.assistantMessage, done.conversation);
  } else if (event === 'error') {
    handlers.onError?.(data as ChatStreamError);
  }
}

/** Turn a non-2xx streaming response into the app's standard error type. */
async function streamError(response: Response): Promise<ApiError> {
  let code = 'provider_unavailable';
  let message = errorMessage(undefined);
  try {
    const body = await response.json();
    const envelope = body?.error;
    if (envelope?.message) message = String(envelope.message);
    if (envelope?.code) code = String(envelope.code);
  } catch {
    /* non-JSON body (proxy error page) — fall back to the generic copy */
  }
  const kind =
    response.status === 401
      ? 'unauthorized'
      : response.status === 403
        ? 'forbidden'
        : response.status === 404
          ? 'not_found'
          : response.status === 429
            ? 'rate_limited'
            : response.status >= 500
              ? 'server'
              : 'unknown';
  return new ApiError(message, { kind, status: response.status, code });
}

/* ── Read-only endpoints ──────────────────────────────────────────── */

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
    signal,
  });
  if (!response.ok) throw await streamError(response);
  return (await response.json()) as T;
}

export const chatApi = {
  capabilities(signal?: AbortSignal): Promise<AICapabilities> {
    return getJson<AICapabilities>('/ai/capabilities', signal);
  },
  usage(windowDays = 30, signal?: AbortSignal): Promise<AIUsageSummary> {
    return getJson<AIUsageSummary>(`/ai/usage?windowDays=${windowDays}`, signal);
  },
};
