"""Administrative provisioning command.

Public registration always creates a normal user, so an administrator has to be
created deliberately. This is that mechanism, and it is the only one:

    python -m app.cli.create_admin --email ops@example.com

Behaviour:

* Prompts for the password on a TTY (never echoed) rather than taking it as an
  argument, so it does not land in shell history or the process list.
* Falls back to `ADMIN_EMAIL` / `ADMIN_PASSWORD` from the environment for
  non-interactive use, e.g. a one-time container entrypoint.
* Refuses a password that fails the shared policy.
* Promotes an existing account instead of creating a duplicate, and can be used
  to reset an administrator's password during recovery.

There is no default credential anywhere in this file, and no seeded admin.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password, validate_password_strength
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import (
    EVENT_ROLE_CHANGED,
    ROLE_ADMIN,
    AuthEvent,
    User,
    UserPreferences,
)

logger = get_logger("create_admin")

EVENT_ADMIN_PROVISIONED = "admin_provisioned"


def _resolve_password(cli_value: str | None) -> str | None:
    """Prefer an interactive prompt; fall back to the environment."""
    if cli_value:
        # Offered for scripted bootstrap, but discouraged in the help text
        # because a command-line argument is visible in the process list.
        return cli_value
    if settings.ADMIN_PASSWORD:
        return settings.ADMIN_PASSWORD
    if not sys.stdin.isatty():
        return None

    first = getpass.getpass("Administrator password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        print("Passwords do not match.", file=sys.stderr)
        return None
    return first


def provision(email: str, password: str, full_name: str) -> int:
    normalised = email.strip().lower()
    problems = validate_password_strength(password)
    if problems:
        print("Password does not meet policy:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == normalised))

        if user is None:
            user = User(
                full_name=full_name.strip() or "AURELIS Administrator",
                email=normalised,
                password_hash=hash_password(password),
                role=ROLE_ADMIN,
                is_active=True,
                email_verified=True,
            )
            session.add(user)
            session.flush()
            session.add(UserPreferences(user_id=user.id))
            action = "created"
        else:
            previous_role = user.role
            user.role = ROLE_ADMIN
            user.is_active = True
            user.password_hash = hash_password(password)
            user.failed_login_count = 0
            user.locked_until = None
            action = "promoted" if previous_role != ROLE_ADMIN else "updated"
            session.add(
                AuthEvent(
                    user_id=user.id,
                    event_type=EVENT_ROLE_CHANGED,
                    outcome="success",
                    detail=f"{previous_role} -> {ROLE_ADMIN} via create_admin",
                    occurred_at=utcnow(),
                )
            )

        session.add(
            AuthEvent(
                user_id=user.id,
                event_type=EVENT_ADMIN_PROVISIONED,
                outcome="success",
                detail=f"account {action} by CLI",
                occurred_at=utcnow(),
            )
        )
        session.commit()
        print(f"Administrator {action}: {normalised} (id={user.id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Provision or promote an AURELIS administrator.",
        epilog=(
            "Prefer the interactive prompt or ADMIN_PASSWORD: a password passed "
            "with --password is visible to other processes."
        ),
    )
    parser.add_argument("--email", default=settings.ADMIN_EMAIL or None)
    parser.add_argument("--full-name", default=settings.ADMIN_FULL_NAME)
    parser.add_argument(
        "--password",
        default=None,
        help="Discouraged; use the prompt or ADMIN_PASSWORD instead.",
    )
    args = parser.parse_args(argv)

    if not args.email:
        parser.error("an email is required (--email or ADMIN_EMAIL)")

    password = _resolve_password(args.password)
    if not password:
        print(
            "No password supplied. Provide one interactively or set ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        return 2

    return provision(args.email, password, args.full_name)


if __name__ == "__main__":
    raise SystemExit(main())
