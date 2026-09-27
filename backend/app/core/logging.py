"""Logging setup.

Structured, level-configurable logging so that MODULE 5 (security hardening)
and MODULE 12 (deployment) can route output without touching call sites.

Every record carries the current request id when one is in scope, so a security
event or an application error can be matched to the response's `X-Request-ID`
without threading the id through every call signature.
"""

import logging
import sys

from app.core.config import settings
from app.core.request_context import current_request_id

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | request_id=%(request_id)s"
)


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record.

    Set as an attribute consumed by `_LOG_FORMAT` rather than appended to
    `record.msg`: a filter can run once per handler, and rewriting the message
    would duplicate the id if a second handler ever sees the same record.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id() or "-"
        return True


def configure_logging() -> None:
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn ships its own handlers; align them instead of duplicating.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
