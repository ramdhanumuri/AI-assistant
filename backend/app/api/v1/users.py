"""Self-service user endpoints.

Everything here operates on the caller's own identity — the user id comes from
the authenticated session, never from the path or the body, so there is no
route that can be pointed at another account.

`/users/me` deliberately duplicates part of `/auth/me`: the brief lists it as
the canonical "who am I" route for the protected surface, and keeping it here
means a client that only needs the profile does not have to fetch preferences.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.cookies import enforce_csrf
from app.api.deps import AuthServiceDep, ClientContextDep, CurrentUser
from app.core.logging import get_logger
from app.schemas.auth import (
    PreferencesRead,
    PreferencesUpdate,
    ProfileUpdate,
    UserRead,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def _user_read(user) -> UserRead:
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserRead, summary="Current user profile")
def get_me(identity: CurrentUser) -> UserRead:
    return _user_read(identity.user)


@router.patch("/me", response_model=UserRead, summary="Update the current user profile")
def update_me(
    payload: ProfileUpdate,
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
    context: ClientContextDep,
) -> UserRead:
    """Update name and avatar.

    A body containing `role`, `is_admin`, `password_hash` or `is_active` is
    rejected with a 422 rather than accepted and ignored — `ProfileUpdate`
    declares only the two mutable fields and forbids extras.
    """
    enforce_csrf(request)
    return _user_read(auth.update_profile(identity.user, payload, context=context))


@router.get(
    "/me/preferences",
    response_model=PreferencesRead,
    summary="Current user preferences",
)
def get_preferences(auth: AuthServiceDep, identity: CurrentUser) -> PreferencesRead:
    return PreferencesRead.model_validate(auth.get_preferences(identity.user))


@router.patch(
    "/me/preferences",
    response_model=PreferencesRead,
    summary="Update the current user preferences",
)
def update_preferences(
    payload: PreferencesUpdate,
    request: Request,
    auth: AuthServiceDep,
    identity: CurrentUser,
) -> PreferencesRead:
    enforce_csrf(request)
    return PreferencesRead.model_validate(
        auth.update_preferences(identity.user, payload)
    )


__all__ = ["router"]
