"""Development entrypoint.

`python run.py` starts uvicorn with reload enabled. Production deployments
should call the ASGI app directly (see README) rather than use reload.
"""

import uvicorn

from app.core.config import settings
from app.main import app  # noqa: F401  (importable for `uvicorn app.main:app`)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )