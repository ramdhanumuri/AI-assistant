"""Administrator endpoints.

Every route in this module depends on `AdminUser`, which is authentication
*plus* a server-side role check against the stored user row. There is no
alternative entry point: nothing here is reachable by a normal user, and no
route accepts a role or an identity from the request.

The `detail` values written to the audit trail are short and non-sensitive —
they never carry a password, a token or a reset link.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.api.cookies import enforce_csrf
from app.api.deps import (
    AdminUser,
    AuthServiceDep,
    ClientContextDep,
    DbSession,
    Pagination,
    user_rate_limit,
)
from app.core.config import settings
from app.core.errors import InvalidRequestError, NotFoundError
from app.core.logging import get_logger
from app.db import supabase
from app.db.base import utcnow
from app.models import (
    EVENT_LOGOUT,
    AIUsageEvent,
    AuthEvent,
    AuthSession,
    Conversation,
    DailyUsage,
    Message,
    User,
)
from app.schemas.ai import AIUsageSummary
from app.schemas.auth import (
    AdminAIUsage,
    AdminEventFeed,
    AdminSystemHealth,
    AdminUsage,
    AdminUserRead,
    AdminUserUpdate,
    AuthEventRead,
    UsageBucket,
)
from app.schemas.common import Page
from app.services.ai import AIService

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"])

VERSION = "2.0.0"


def _admin_user_read(user: User, *, active_sessions: int, conversation_count: int) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        failed_login_count=user.failed_login_count,
        locked_until=user.locked_until,
        active_sessions=active_sessions,
        conversation_count=conversation_count,
    )


@router.get("/users", response_model=Page[AdminUserRead], summary="List accounts")
def list_users(
    db: DbSession,
    _: AdminUser,
    pagination: Pagination,
    search: str | None = Query(default=None, description="Substring match on name or email."),
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    is_active: bool | None = Query(default=None),
) -> Page[AdminUserRead]:
    """Paginated account list with per-user session and thread counts.

    The password hash is not part of `AdminUserRead`, so it cannot be returned
    even to an administrator.
    """
    conditions = []
    if search:
        needle = f"%{search.strip().lower()}%"
        conditions.append(
            func.lower(User.email).like(needle) | func.lower(User.full_name).like(needle)
        )
    if role:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))

    total = int(
        db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    )
    users = list(
        db.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
    )

    now = utcnow()
    session_counts = dict(
        db.execute(
            select(AuthSession.user_id, func.count(AuthSession.id))
            .where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
            .group_by(AuthSession.user_id)
        ).all()
    )
    conversation_counts = dict(
        db.execute(
            select(Conversation.owner_id, func.count(Conversation.id))
            .where(Conversation.owner_id.is_not(None))
            .group_by(Conversation.owner_id)
        ).all()
    )

    items = [
        _admin_user_read(
            user,
            active_sessions=int(session_counts.get(user.id, 0)),
            conversation_count=int(conversation_counts.get(user.id, 0)),
        )
        for user in users
    ]
    return Page[AdminUserRead](
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/users/{user_id}", response_model=AdminUserRead, summary="Get one account")
def get_user(user_id: str, db: DbSession, _: AdminUser) -> AdminUserRead:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("That account does not exist.")
    now = utcnow()
    sessions = int(
        db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
        or 0
    )
    conversations = int(
        db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.owner_id == user.id)
        )
        or 0
    )
    return _admin_user_read(
        user, active_sessions=sessions, conversation_count=conversations
    )


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserRead,
    summary="Change an account's role or active state",
)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    db: DbSession,
    auth: AuthServiceDep,
    identity: AdminUser,
    context: ClientContextDep,
) -> AdminUserRead:
    """The only path to a role change, and it is admin-gated.

    A demotion or a deactivation revokes the target's sessions immediately, so
    the change takes effect on their next request rather than at token expiry.
    """
    enforce_csrf(request)
    user_rate_limit(identity, scope="admin")

    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("That account does not exist.")

    if payload.role is not None:
        target = auth.set_role(identity.user, target, payload.role, context=context)
    if payload.is_active is not None:
        target = auth.set_active(identity.user, target, payload.is_active, context=context)

    return get_user(target.id, db, identity)


@router.get("/usage", response_model=AdminUsage, summary="Aggregate platform usage")
def usage(db: DbSession, _: AdminUser) -> AdminUsage:
    now = utcnow()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(hours=24)

    def count(model, *conditions) -> int:
        return int(
            db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
        )

    daily = list(db.scalars(select(DailyUsage).order_by(DailyUsage.day)))

    return AdminUsage(
        total_users=count(User),
        active_users=count(User, User.is_active.is_(True)),
        admin_users=count(User, User.role == "admin"),
        new_users_7d=count(User, User.created_at >= week_ago),
        total_conversations=count(Conversation),
        total_messages=count(Message),
        active_sessions=count(
            AuthSession, AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
        ),
        sessions_created_24h=count(AuthSession, AuthSession.created_at >= day_ago),
        auth_events_24h=count(AuthEvent, AuthEvent.occurred_at >= day_ago),
        failed_logins_24h=count(
            AuthEvent,
            AuthEvent.event_type == "login_failure",
            AuthEvent.occurred_at >= day_ago,
        ),
        usage=[
            UsageBucket(label=row.label, value=row.value, secondary=row.secondary)
            for row in daily
        ],
    )


@router.get("/events", response_model=AdminEventFeed, summary="Authentication audit feed")
def events(
    db: DbSession,
    _: AdminUser,
    pagination: Pagination,
    event_type: str | None = Query(default=None, description="Filter by event type."),
    outcome: str | None = Query(default=None, pattern="^(success|failure|denied)$"),
) -> AdminEventFeed:
    """Recent authentication events.

    Only keyed digests of the email and address are stored, so this feed is
    correlatable without being a list of accounts and IPs.
    """
    conditions = []
    if event_type:
        conditions.append(AuthEvent.event_type == event_type)
    if outcome:
        conditions.append(AuthEvent.outcome == outcome)

    total = int(
        db.scalar(select(func.count()).select_from(AuthEvent).where(*conditions)) or 0
    )
    rows = list(
        db.scalars(
            select(AuthEvent)
            .where(*conditions)
            .order_by(AuthEvent.occurred_at.desc(), AuthEvent.id.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
    )
    counts = dict(
        db.execute(
            select(AuthEvent.event_type, func.count(AuthEvent.id)).group_by(
                AuthEvent.event_type
            )
        ).all()
    )

    return AdminEventFeed(
        items=[AuthEventRead.model_validate(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        counts_by_type={str(k): int(v) for k, v in counts.items()},
    )


@router.get(
    "/ai-usage",
    response_model=AdminAIUsage,
    summary="Platform-wide AI usage and cost",
)
def ai_usage(
    db: DbSession,
    _: AdminUser,
    window_days: int | None = Query(
        default=30, ge=1, le=365, description="Rolling window in days; omit for all time."
    ),
) -> AdminAIUsage:
    """Aggregate model usage across the platform.

    Counts, tokens and latency only — never conversation content. This is the
    foundation the Step 10 dashboard builds on, and it is deliberately aggregate
    so it does not become a way to read private threads.
    """
    service = AIService(db)
    summary = service.usage_summary(user_id=None, window_days=window_days)
    models = dict(
        db.execute(
            select(AIUsageEvent.model, func.count(AIUsageEvent.id)).group_by(
                AIUsageEvent.model
            )
        ).all()
    )
    providers = dict(
        db.execute(
            select(AIUsageEvent.provider, func.count(AIUsageEvent.id)).group_by(
                AIUsageEvent.provider
            )
        ).all()
    )
    return AdminAIUsage(
        summary=summary,
        models_by_use={str(k): int(v) for k, v in models.items()},
        providers_by_use={str(k): int(v) for k, v in providers.items()},
    )


@router.get(
    "/system-health",
    response_model=AdminSystemHealth,
    summary="Deployment and authentication health",
)
def system_health(db: DbSession, _: AdminUser) -> AdminSystemHealth:
    """Operational view for administrators.

    Reports *whether* secrets and providers are configured, never their values.
    """
    database = "ok"
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001  (any driver failure means unavailable)
        database = "unavailable"

    from app.services import mailer

    return AdminSystemHealth(
        status="ok" if database == "ok" else "degraded",
        environment=settings.APP_ENV,
        version=VERSION,
        database=database,
        database_dialect=settings.DATABASE_URL.split("://", 1)[0],
        supabase=supabase.probe(),
        ai_provider=settings.AI_PROVIDER,
        ai_model=settings.ai_model_resolved or None,
        ai_configured=settings.ai_configured,
        ai_streaming_enabled=settings.AI_STREAMING_ENABLED,
        auth_secret_configured=bool(settings.AUTH_SECRET),
        cookie_secure=settings.is_cookie_secure,
        cookie_samesite=settings.cookie_samesite,
        access_token_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        password_hashing="argon2id",
        mail_configured=mailer.is_configured(),
        checked_at=utcnow(),
    )


@router.get(
    "/users/{user_id}/sessions",
    response_model=list[dict],
    summary="List an account's active sessions",
)
def user_sessions(user_id: str, db: DbSession, _: AdminUser) -> list[dict]:
    now = utcnow()
    rows = list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.created_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "createdAt": int(row.created_at.timestamp() * 1000),
            "expiresAt": int(row.expires_at.timestamp() * 1000),
            "lastUsedAt": (
                int(row.last_used_at.timestamp() * 1000) if row.last_used_at else None
            ),
            "userAgent": row.user_agent,
        }
        for row in rows
    ]


@router.post(
    "/users/{user_id}/sessions/revoke",
    response_model=dict,
    summary="Force an account to sign out everywhere",
)
def revoke_user_sessions(
    user_id: str,
    request: Request,
    db: DbSession,
    auth: AuthServiceDep,
    identity: AdminUser,
    context: ClientContextDep,
) -> dict:
    enforce_csrf(request)
    user_rate_limit(identity, scope="admin")
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("That account does not exist.")

    revoked = auth.revoke_all_sessions(target.id)
    auth.record_event(
        EVENT_LOGOUT,
        user=target,
        context=context,
        detail=f"revoked {revoked} session(s) by administrator",
        commit=True,
    )
    return {"revoked": revoked}


__all__ = ["router"]
