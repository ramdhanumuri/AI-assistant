"""Model registry.

Importing this package registers every mapper on `Base.metadata`, which
Alembic autogenerate and `create_all()` both depend on. Keep the imports
explicit — a missing entry silently drops a table from migrations.
"""

from app.models.conversation import AIUsageEvent, Conversation, Message
from app.models.knowledge import KnowledgeSource
from app.models.memory import MemoryRecord
from app.models.mode import AIMode
from app.models.project import Project
from app.models.telemetry import ActivityEvent, DailyUsage
from app.models.tool import ToolIntegration
from app.models.user import (
    EVENT_ACCOUNT_DEACTIVATED,
    EVENT_ACCOUNT_REACTIVATED,
    EVENT_ADMIN_PROVISIONED,
    EVENT_AUTHZ_DENIED,
    EVENT_CSRF_FAILURE,
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_LOCKED,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    EVENT_PASSWORD_CHANGED,
    EVENT_PASSWORD_RESET_COMPLETED,
    EVENT_PASSWORD_RESET_REQUESTED,
    EVENT_PROFILE_UPDATED,
    EVENT_RATE_LIMITED,
    EVENT_REGISTERED,
    EVENT_ROLE_CHANGED,
    EVENT_SESSION_REVOKED,
    EVENT_SUSPICIOUS_ACTIVITY,
    EVENT_TOKEN_REFRESHED,
    EVENT_TOKEN_REUSE_DETECTED,
    EVENT_TYPES,
    EVENT_UPLOAD_REJECTED,
    ROLE_ADMIN,
    ROLE_USER,
    ROLES,
    AuthEvent,
    AuthSession,
    PasswordResetToken,
    User,
    UserPreferences,
)

__all__ = [
    "AIUsageEvent",
    "AIMode",
    "ActivityEvent",
    "AuthEvent",
    "AuthSession",
    "Conversation",
    "DailyUsage",
    "EVENT_ACCOUNT_DEACTIVATED",
    "EVENT_ACCOUNT_REACTIVATED",
    "EVENT_ADMIN_PROVISIONED",
    "EVENT_AUTHZ_DENIED",
    "EVENT_CSRF_FAILURE",
    "EVENT_LOGIN_FAILURE",
    "EVENT_LOGIN_LOCKED",
    "EVENT_LOGIN_SUCCESS",
    "EVENT_LOGOUT",
    "EVENT_PASSWORD_CHANGED",
    "EVENT_PASSWORD_RESET_COMPLETED",
    "EVENT_PASSWORD_RESET_REQUESTED",
    "EVENT_PROFILE_UPDATED",
    "EVENT_RATE_LIMITED",
    "EVENT_REGISTERED",
    "EVENT_ROLE_CHANGED",
    "EVENT_SESSION_REVOKED",
    "EVENT_SUSPICIOUS_ACTIVITY",
    "EVENT_TOKEN_REFRESHED",
    "EVENT_TOKEN_REUSE_DETECTED",
    "EVENT_TYPES",
    "EVENT_UPLOAD_REJECTED",
    "KnowledgeSource",
    "MemoryRecord",
    "Message",
    "PasswordResetToken",
    "Project",
    "ROLE_ADMIN",
    "ROLE_USER",
    "ROLES",
    "ToolIntegration",
    "User",
    "UserPreferences",
]
