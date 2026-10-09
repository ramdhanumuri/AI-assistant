"""Server-Sent Events framing.

A deliberately small encoder for the AI streaming endpoint. SSE is chosen over
WebSockets because it is a one-way server→client stream over ordinary HTTP: it
works through the existing CORS, cookie and CSRF setup with no second protocol,
no new handshake and no new authentication surface.

Frames follow the SSE wire format:

    event: delta
    data: {"text":"…"}

Two details that matter for correctness:

* `data` is JSON, so a message containing a newline (or any Unicode) cannot
  break the framing — a raw newline in the payload would terminate the field.
  `ensure_ascii=False` keeps Telugu and emoji intact rather than escaping them.
* A heartbeat comment (`: keep-alive`) is emitted for long idle gaps so an
  intermediary proxy does not close a connection that is merely waiting on a
  slow model.
"""

from __future__ import annotations

import json
from typing import Any

# A comment line. SSE ignores anything starting with ':'; it exists purely to
# keep the socket warm through a proxy's idle timeout.
HEARTBEAT = ": keep-alive\n\n"


def sse_event(event: str, data: dict[str, Any] | None = None) -> str:
    """Encode one named event. `data` is serialised as JSON on a single line."""
    payload = json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


__all__ = ["HEARTBEAT", "sse_event"]
