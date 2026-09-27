"""File-upload validation and safe storage-path construction.

Step 8 will add real uploads. This module is the part that must exist *before*
any byte is written, because every mistake it prevents is a class of bug that is
much harder to retrofit:

* **User input never becomes a path component.** The stored name is a
  server-generated id plus an extension drawn from an allow-list, so
  `../../etc/passwd`, `..\\..\\secret.txt`, a null byte, a Windows device name
  (`CON`, `NUL`) or a 4 KB filename are all just rejected or ignored rather than
  reaching the filesystem.
* **The resolved path is re-checked against the storage root.** Even with a
  generated name, `resolve()` + `is_relative_to(root)` is the final guard, so a
  symlinked storage directory or a future code change cannot silently escape.
* **Extension and MIME are checked independently.** Browsers send a
  `Content-Type` that the client controls, so it is a hint, not proof; the
  extension is the second opinion. Neither alone is sufficient, and neither is
  trusted to be executable-free — files are stored outside the web root.

Nothing here writes to disk; the caller does that once validation passes. There
is deliberately no "accept anything" fallback: an unconfigured storage dir
means uploads are refused (see `settings.uploads_enabled`).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.errors import InvalidRequestError

# Extension → the MIME types that may claim it. The check is
# "is the declared MIME allowed *and* is the extension one this MIME may use",
# so `evil.png` that declares `text/html` is refused even though `.png` is on
# the list.
_EXTENSION_MIME: dict[str, frozenset[str]] = {
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".gif": frozenset({"image/gif"}),
    ".webp": frozenset({"image/webp"}),
    ".pdf": frozenset({"application/pdf"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".csv": frozenset({"text/csv", "text/plain"}),
}

# Extensions that are never acceptable regardless of declared MIME. Kept as a
# belt-and-braces deny-list on top of the allow-list above; the allow-list is
# what actually decides.
_DANGEROUS_EXTENSIONS = frozenset(
    {
        ".php", ".phtml", ".py", ".rb", ".pl", ".sh", ".bash", ".zsh",
        ".exe", ".dll", ".so", ".bat", ".cmd", ".com", ".msi", ".jar",
        ".js", ".mjs", ".cjs", ".html", ".htm", ".svg", ".xml", ".htaccess",
    }
)

# Windows reserved device names — illegal as a filename on that platform even
# with an extension.
_WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

_MAX_FILENAME_LENGTH = 255
_SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ValidatedUpload:
    """The result of validation: a safe basename and the metadata to persist."""

    original_name: str
    stored_name: str
    extension: str
    content_type: str
    size_bytes: int

    def relative_path(self, owner_id: str) -> Path:
        """Per-owner relative path. Never contains a client-supplied segment."""
        return Path(_safe_owner_segment(owner_id)) / self.stored_name


def _safe_owner_segment(owner_id: str) -> str:
    """Reduce an owner id to a single safe path segment.

    Owner ids are server-generated UUIDs today, but this makes that an
    invariant rather than a coincidence.
    """
    cleaned = _SAFE_STEM.sub("-", owner_id.strip())
    return cleaned[:64] or "unknown"


def sanitise_filename(raw: str) -> str:
    """Return a display-safe form of a client filename.

    Used only for the human-readable `original_name` we echo back in metadata;
    it never becomes part of a path. Control characters, path separators and
    Unicode direction overrides are stripped so the stored label cannot disguise
    itself or carry a traversal sequence.
    """
    # NFKC folds look-alikes; strip control characters afterwards.
    normalised = unicodedata.normalize("NFKC", raw)
    # Drop any path: keep only the final component, handling both separators.
    leaf = normalised.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in leaf if ch.isprintable() and ch not in "\x00")
    cleaned = _SAFE_STEM.sub("_", cleaned).strip("._-")
    return cleaned[:_MAX_FILENAME_LENGTH] or "upload"


def _extension_of(name: str) -> str:
    return Path(name).suffix.lower()


def validate_upload(
    *,
    filename: str,
    content_type: str | None,
    size_bytes: int,
) -> ValidatedUpload:
    """Validate one upload and mint a safe stored name.

    Raises `InvalidRequestError` (422) for anything that fails, with a message
    that names the rule but never echoes the raw filename back.
    """
    if not settings.uploads_enabled:
        raise InvalidRequestError("File uploads are not enabled on this deployment.")

    if size_bytes <= 0:
        raise InvalidRequestError("The uploaded file is empty.")
    if size_bytes > settings.MAX_UPLOAD_BYTES:
        raise InvalidRequestError(
            f"The uploaded file exceeds the {settings.MAX_UPLOAD_BYTES} byte limit."
        )

    safe_display = sanitise_filename(filename or "")
    extension = _extension_of(safe_display)

    if extension in _DANGEROUS_EXTENSIONS:
        raise InvalidRequestError("That file type is not permitted.")
    if not extension:
        raise InvalidRequestError("The file must have a recognised extension.")

    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared not in settings.ALLOWED_UPLOAD_MIME_TYPES:
        raise InvalidRequestError("That content type is not permitted.")

    permitted_mimes = _EXTENSION_MIME.get(extension)
    if permitted_mimes is None:
        raise InvalidRequestError("That file type is not permitted.")
    if declared not in permitted_mimes:
        # The extension and the declared type disagree — a classic polyglot
        # upload. Refuse rather than pick a winner.
        raise InvalidRequestError("The file's type does not match its extension.")

    stem = Path(safe_display).stem.lower()
    if stem in _WINDOWS_RESERVED:
        raise InvalidRequestError("That filename is not permitted.")

    # The stored name is server-generated: the client's name never reaches the
    # filesystem, so traversal and reserved names are structurally impossible.
    stored_name = f"{uuid.uuid4().hex}{extension}"

    return ValidatedUpload(
        original_name=safe_display,
        stored_name=stored_name,
        extension=extension,
        content_type=declared,
        size_bytes=size_bytes,
    )


def resolve_storage_path(relative_path: Path) -> Path:
    """Join a validated relative path to the storage root, safely.

    Even though `relative_path` is server-generated, the resolved result is
    checked to be inside the root: defence in depth against a symlinked storage
    directory or a future caller that passes something less trustworthy.
    """
    root = Path(settings.UPLOAD_STORAGE_DIR).expanduser().resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise InvalidRequestError("The upload path is invalid.")
    return candidate


__all__ = [
    "ValidatedUpload",
    "resolve_storage_path",
    "sanitise_filename",
    "validate_upload",
]
