"""Application configuration.

Settings are read from environment variables (and an optional `.env` file)
so that the same image runs unchanged across development and production.
Later modules extend this file rather than introducing a second config path.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# A signing key must be long enough that guessing it is infeasible. 32 bytes
# (256 bits) is the floor for HS256; anything shorter is rejected at startup.
MIN_AUTH_SECRET_LENGTH = 32

# Anything that is not one of these is treated as a deployed environment.
_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "test", "local"})

# Signing keys that ship in documentation, examples or tests. Accepting one of
# these in a non-development environment would make every token forgeable, so
# they are rejected unless APP_ENV is development/test.
_PLACEHOLDER_SECRETS = frozenset(
    {
        "change-me",
        "changeme",
        "replace-me",
        "secret",
        "dev-secret",
        "test-secret",
        "insecure",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "AURELIS Intelligence API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    # Comma-separated in the environment; split by the validator below.
    # `NoDecode` keeps pydantic-settings from JSON-decoding a `list[str]` env
    # value before the validator runs, so `a,b` parses as documented.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:12000",
        "http://127.0.0.1:12000",
    ]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 12001

    # ── Authentication (MODULE 4) ─────────────────────────────────────
    # HMAC key for the access-token signature. Generated per deployment; the
    # default exists only so a developer can run the API without a `.env`, and
    # is refused once APP_ENV leaves development/test.
    AUTH_SECRET: str = "aurelis-development-only-insecure-signing-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    # Password-reset tokens are deliberately short-lived and single-use.
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # Argon2id work factor. RFC 9106's second recommended option; raise it as
    # hardware improves — stored hashes carry their own parameters, so raising
    # this does not invalidate existing passwords.
    PASSWORD_HASH_MEMORY_KIB: int = 65536
    PASSWORD_HASH_TIME_COST: int = 3
    PASSWORD_HASH_PARALLELISM: int = 4

    # ── Session cookies ───────────────────────────────────────────────
    # Both tokens travel in HttpOnly cookies. `lax` is the correct default for
    # a first-party SPA; a cross-site deployment needs `none`, which browsers
    # only honour together with `secure`.
    AUTH_COOKIE_NAME: str = "aurelis_session"
    REFRESH_COOKIE_NAME: str = "aurelis_refresh"
    CSRF_COOKIE_NAME: str = "aurelis_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    COOKIE_DOMAIN: str = ""
    COOKIE_SAMESITE: str = "lax"
    # None ⇒ derived from APP_ENV: secure outside development/test.
    COOKIE_SECURE: bool | None = None
    # HSTS lifetime. Only emitted over HTTPS (see security_headers.py); raise
    # this deliberately, since browsers cache it and the change is not quick to
    # undo.
    HSTS_MAX_AGE_SECONDS: int = 31_536_000

    # ── Abuse controls ────────────────────────────────────────────────
    AUTH_RATE_LIMIT_ATTEMPTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AUTH_MAX_FAILED_LOGINS: int = 10
    AUTH_LOCKOUT_SECONDS: int = 900

    # Optional shared store for rate limiting. When set, counters live in Redis
    # so every worker shares one budget; when empty the in-process limiter is
    # used (correct for a single worker, degrade-only for several).
    REDIS_URL: str = ""
    # Generous guard rails for the general (non-auth) API throttle. See
    # `app/core/ratelimit.py` for the per-scope budgets these bound.
    GENERAL_RATE_LIMIT_ATTEMPTS: int = 600
    GENERAL_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ── Request handling ──────────────────────────────────────────────
    # Ceiling for JSON request bodies, enforced before the body is parsed so a
    # multi-megabyte payload cannot be buffered into memory.
    MAX_REQUEST_BODY_BYTES: int = 1_048_576
    # Swagger/ReDoc/OpenAPI are served in development and hidden outside it by
    # default. Set explicitly to re-expose them (e.g. behind an internal network).
    ENABLE_API_DOCS: bool | None = None

    # ── File uploads (Step 8 foundation) ──────────────────────────────
    # When empty, uploads are disabled by default: routes that require the
    # validator refuse rather than writing somewhere unexpected.
    UPLOAD_STORAGE_DIR: str = ""
    MAX_UPLOAD_BYTES: int = 10_485_760
    ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/csv",
    ]

    # ── Provisioning ──────────────────────────────────────────────────
    # One-time bootstrap administrator. Read only by
    # `python -m app.cli.create_admin`; never seeded, never hard-coded.
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_FULL_NAME: str = "AURELIS Administrator"

    # Database
    DATABASE_URL: str = "sqlite:///./aurelis.db"

    # Supabase (MODULE 3). These are consumed by the REST/Realtime layer and by
    # the readiness probe; SQLAlchemy keeps talking to DATABASE_URL directly.
    # The service-role key bypasses Row Level Security, so it is server-only
    # and must never be shipped to the browser.
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # ── Model layer (STEP 6) ──────────────────────────────────────────
    # `simulator` is the deterministic offline engine used by tests and local
    # development. A real provider (`openai`, or any OpenAI-compatible
    # endpoint) is selected here and never from the client.
    AI_PROVIDER: str = "simulator"
    # Credentials live only in the process environment. They are never
    # serialised into a response, a log line or the frontend bundle.
    AI_PROVIDER_API_KEY: str = ""
    # Override for OpenAI-compatible gateways (Azure, vLLM, OpenRouter, …).
    # Empty ⇒ the provider's official default endpoint.
    AI_BASE_URL: str = ""
    AI_MODEL: str = ""
    AI_DEFAULT_MODEL: str = ""
    # Comma-separated in the environment; split by the validator below.
    # `NoDecode` is required: pydantic-settings otherwise tries to JSON-decode a
    # `list[str]` env value *before* field validators run, so the documented
    # `AI_ALLOWED_MODELS=a,b` form would fail to parse at boot.
    AI_ALLOWED_MODELS: Annotated[list[str], NoDecode] = []
    # Every provider call is bounded; nothing is allowed to hang forever.
    AI_TIMEOUT_SECONDS: float = 60.0
    AI_MAX_OUTPUT_TOKENS: int = 1024
    # Budget for the prompt assembled from system + history + current turn.
    AI_MAX_INPUT_TOKENS: int = 8192
    AI_TEMPERATURE: float = 0.7
    AI_TOP_P: float = 1.0
    AI_STREAMING_ENABLED: bool = True
    # How many prior messages (user + assistant) may be replayed as context.
    AI_MAX_CONTEXT_MESSAGES: int = 20
    # Retries are only ever applied to transient failures (see app/ai/base.py).
    AI_MAX_RETRIES: int = 2
    AI_RETRY_BACKOFF_SECONDS: float = 0.5
    # Optional operator override of the system prompt. Kept server-side.
    AI_SYSTEM_PROMPT: str = ""
    # Title generation is an optional side task; it must never block the reply.
    AI_TITLE_GENERATION_ENABLED: bool = True
    AI_TITLE_MAX_TOKENS: int = 24
    # Cost foundation. Left at zero unless a deployment knows its real pricing;
    # a zero price means "cost not recorded", never a fabricated number.
    AI_INPUT_COST_PER_MILLION: float = 0.0
    AI_OUTPUT_COST_PER_MILLION: float = 0.0
    AI_COST_CURRENCY: str = "USD"
    AI_PRICING_VERSION: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("AI_ALLOWED_MODELS", mode="before")
    @classmethod
    def _split_models(cls, value: object) -> object:
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value

    @field_validator("AI_TEMPERATURE")
    @classmethod
    def _temperature_range(cls, value: float) -> float:
        # Rejected at boot rather than per request: a nonsensical value is a
        # deployment mistake, and failing fast beats a provider 400 storm.
        if not 0.0 <= value <= 2.0:
            raise ValueError("AI_TEMPERATURE must be between 0 and 2")
        return value

    @field_validator("AI_TOP_P")
    @classmethod
    def _top_p_range(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError("AI_TOP_P must be greater than 0 and at most 1")
        return value

    @field_validator(
        "AI_MAX_OUTPUT_TOKENS",
        "AI_MAX_INPUT_TOKENS",
        "AI_MAX_CONTEXT_MESSAGES",
        "AI_TITLE_MAX_TOKENS",
    )
    @classmethod
    def _positive_budget(cls, value: int) -> int:
        if value < 1:
            raise ValueError("token and context budgets must be at least 1")
        return value

    @field_validator("AI_MAX_RETRIES")
    @classmethod
    def _retry_bounds(cls, value: int) -> int:
        # Bounded so a misconfiguration cannot become a retry storm.
        if not 0 <= value <= 5:
            raise ValueError("AI_MAX_RETRIES must be between 0 and 5")
        return value

    @field_validator("AI_TIMEOUT_SECONDS", "AI_RETRY_BACKOFF_SECONDS")
    @classmethod
    def _positive_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeouts and backoff must be positive")
        return value

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def _known_samesite(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be 'lax', 'strict' or 'none'")
        return normalised

    @model_validator(mode="after")
    def _validate_auth_configuration(self) -> "Settings":
        # Checked in every environment: a SameSite=None cookie without Secure is
        # silently dropped by the browser, so the developer would see a
        # mysterious "logged out on every request" rather than a clear error.
        if self.cookie_samesite == "none" and not self.is_cookie_secure:
            raise ValueError("SameSite=None requires Secure cookies")

        if self.APP_ENV.strip().lower() in _LOCAL_ENVIRONMENTS:
            # A developer must be able to run the API with no `.env` at all.
            return self

        # Anything that is not a local environment is treated as deployed, and
        # these defaults are all fatal in that case.
        if len(self.AUTH_SECRET) < MIN_AUTH_SECRET_LENGTH:
            raise ValueError(
                "AUTH_SECRET must be at least "
                f"{MIN_AUTH_SECRET_LENGTH} characters outside development"
            )
        # Substring rather than equality: the shipped development default
        # (`aurelis-development-only-insecure-signing-key`) must be refused too,
        # not only the bare literals.
        lowered = self.AUTH_SECRET.strip().lower()
        for marker in _PLACEHOLDER_SECRETS:
            if marker in lowered:
                raise ValueError(
                    f"AUTH_SECRET contains the placeholder value '{marker}'; "
                    "generate a real key"
                )
        if self.COOKIE_SECURE is False:
            raise ValueError("COOKIE_SECURE must be true outside development")
        # DEBUG is the single most common production leak: it turns every
        # unexpected exception into a traceback and makes the interactive docs
        # a debugging surface.
        if self.DEBUG:
            raise ValueError("DEBUG must be false outside development")
        # Credentialed CORS with a wildcard origin is both invalid per the spec
        # and a silent way to let any website drive authenticated requests.
        if "*" in self.CORS_ORIGINS:
            raise ValueError(
                "CORS_ORIGINS must not contain '*' outside development; "
                "list the trusted origins explicitly"
            )
        for origin in self.CORS_ORIGINS:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"CORS origin '{origin}' must be an http(s) URL")
        self._validate_deployment_urls()
        return self

    def _validate_deployment_urls(self) -> None:
        """Reject a plaintext HTTP public URL outside development."""
        for label, value in (
            ("SUPABASE_URL", self.SUPABASE_URL),
            ("REDIS_URL", self.REDIS_URL),
        ):
            if value.strip().lower().startswith("http://"):
                raise ValueError(f"{label} must use https outside development")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() not in _LOCAL_ENVIRONMENTS

    @property
    def uploads_enabled(self) -> bool:
        return bool(self.UPLOAD_STORAGE_DIR.strip())

    @property
    def docs_enabled(self) -> bool:
        """Explicit config wins; otherwise only in local environments."""
        if self.ENABLE_API_DOCS is not None:
            return self.ENABLE_API_DOCS
        return not self.is_production

    @property
    def cookie_samesite(self) -> str:
        return self.COOKIE_SAMESITE.strip().lower()

    @property
    def is_cookie_secure(self) -> bool:
        """Secure by default outside development; explicit config always wins."""
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.is_production

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_supabase_configured(self) -> bool:
        """True when the REST/Realtime layer has enough config to be used."""
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    @property
    def ai_model_resolved(self) -> str:
        """The model the server will use, resolved in one place.

        Precedence: an explicit `AI_MODEL`, then `AI_DEFAULT_MODEL`, then the
        first allow-listed model. An empty result means the provider itself
        decides — and a real provider treats that as a configuration error.
        """
        for candidate in (self.AI_MODEL, self.AI_DEFAULT_MODEL):
            if candidate.strip():
                return candidate.strip()
        return self.AI_ALLOWED_MODELS[0] if self.AI_ALLOWED_MODELS else ""

    @property
    def ai_allowed_models(self) -> list[str]:
        """Models the server will accept. The client never widens this set."""
        models = list(self.AI_ALLOWED_MODELS)
        resolved = self.ai_model_resolved
        if resolved and resolved not in models:
            models.insert(0, resolved)
        return models

    @property
    def ai_configured(self) -> bool:
        """Whether the configured provider has everything it needs to run.

        Used to answer health questions without ever revealing the key itself.
        """
        if self.AI_PROVIDER.strip().lower() in {"simulator", "local"}:
            return True
        return bool(self.AI_PROVIDER_API_KEY.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so config is parsed once per process."""
    return Settings()


settings = get_settings()
