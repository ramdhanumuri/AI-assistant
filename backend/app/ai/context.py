"""Context-window construction.

Turns a conversation transcript into the exact message list a provider will
receive. It is the only place that decides what history is sent, so the two
failure modes it exists to prevent cannot happen anywhere else:

* sending the entire database transcript forever (unbounded cost and an
  eventual hard provider rejection), and
* truncating the *current* user message (which would silently answer a
  different question than the one asked).

Order of operations, and why:

1. Start from the system message — it is never dropped.
2. Append the most recent prior turns, oldest-first, up to
   `AI_MAX_CONTEXT_MESSAGES` *and* within the token budget.
3. Append the current user message last.
4. If the system message plus the current message alone exceed
   `AI_MAX_INPUT_TOKENS`, raise `ContextTooLargeError` rather than trimming
   either. A prompt that is over budget with no history is a genuine
   "conversation too large" condition and must be reported, not quietly
   mangled.

Older messages are removed whole, never split: half a prior turn is worse than
no prior turn, because it can invert the meaning of what remains.
"""

from __future__ import annotations

import math

from app.ai.errors import ContextTooLargeError
from app.ai.types import ChatMessage
from app.core.config import settings

# Estimation constants. We deliberately do not pull in a tokeniser dependency
# for Step 6: the budget exists to stop an oversized request reaching the
# provider, and a conservative estimate achieves that without coupling the
# codebase to one vendor's tokeniser (which would be wrong for another
# provider's model anyway). Latin text averages ~4 characters per token;
# non-Latin scripts — Telugu, CJK — tokenise far less efficiently, so they are
# charged at roughly one token per character. The estimate errs high.
_ASCII_CHARS_PER_TOKEN = 4.0
_NON_ASCII_TOKENS_PER_CHAR = 1.0


def estimate_tokens(text: str) -> int:
    """A conservative token estimate for one string.

    Overestimates rather than under, so the budget protects the provider
    request. Returns 0 for empty input.
    """
    if not text:
        return 0
    ascii_chars = 0
    non_ascii_chars = 0
    for char in text:
        if ord(char) < 128:
            ascii_chars += 1
        else:
            non_ascii_chars += 1
    estimate = ascii_chars / _ASCII_CHARS_PER_TOKEN
    estimate += non_ascii_chars * _NON_ASCII_TOKENS_PER_CHAR
    # A small per-message overhead for role/delimiter tokens.
    return int(math.ceil(estimate)) + 4


def estimate_messages(messages: list[ChatMessage]) -> int:
    return sum(estimate_tokens(message.content) for message in messages)


def build_context(
    *,
    system_message: ChatMessage,
    history: list[ChatMessage],
    current_user_message: str,
) -> list[ChatMessage]:
    """Assemble the provider message list within the configured budgets.

    `history` is the prior transcript, oldest-first, already flattened to
    plain text. It may be longer than the budget; older entries are dropped
    from the front until it fits.
    """
    max_messages = settings.AI_MAX_CONTEXT_MESSAGES
    max_tokens = settings.AI_MAX_INPUT_TOKENS

    current = ChatMessage(role="user", content=current_user_message)

    # The system prompt and the current turn are non-negotiable. If those two
    # alone do not fit, the request cannot be answered honestly.
    reserved = estimate_tokens(system_message.content) + estimate_tokens(current.content)
    if reserved > max_tokens:
        raise ContextTooLargeError(
            internal_detail=(
                f"system+current={reserved} tokens exceeds AI_MAX_INPUT_TOKENS={max_tokens}"
            )
        )

    budget = max_tokens - reserved

    # Most recent turns first, so the newest context wins when trimming.
    selected: list[ChatMessage] = []
    used = 0
    for message in reversed(history):
        if len(selected) >= max_messages:
            break
        cost = estimate_tokens(message.content)
        if used + cost > budget:
            # Stop rather than skip: keeping an *older* message while dropping a
            # newer one would present the model with a non-contiguous history.
            break
        selected.append(message)
        used += cost

    selected.reverse()
    return [system_message, *selected, current]


__all__ = ["build_context", "estimate_messages", "estimate_tokens"]
