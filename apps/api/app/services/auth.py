"""Session lifecycle: create users, issue and rotate refresh tokens, revoke sessions."""

import logging
from datetime import timedelta

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import schemas
from app.config import get_settings
from app.db import utcnow
from app.errors import ApiError
from app.models import RefreshToken, User, UserPreferences, prefixed_id
from app.security import create_access_token, hash_password, hash_token, new_opaque_token

log = logging.getLogger(__name__)

REFRESH_COOKIE = "vysel_refresh"
# Two tabs refreshing at once present the same token; the loser is not an attacker.
REUSE_GRACE_SECONDS = 10


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, *, email: str, display_name: str, password: str | None, email_verified: bool = False) -> User:
    user = User(
        email=normalize_email(email),
        display_name=display_name,
        password_hash=hash_password(password) if password else None,
        email_verified=email_verified,
        preferences=UserPreferences(),
    )
    db.add(user)
    db.flush()
    return user


def to_profile(user: User) -> schemas.Profile:
    prefs = user.preferences or UserPreferences(style_goals=[], occasions=[], categories=[])
    return schemas.Profile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified=user.email_verified,
        has_password=user.password_hash is not None,
        auth_providers=sorted({a.provider for a in user.oauth_accounts} | ({"password"} if user.password_hash else set())),
        preferences=schemas.Preferences.model_validate(prefs),
        onboarding_completed=prefs.onboarding_completed_at is not None,
        is_admin=user.email.lower() in get_settings().admin_email_allowlist,
        created_at=user.created_at,
        updated_at=max(user.updated_at, prefs.updated_at) if prefs.updated_at else user.updated_at,
    )


# ── Cookies ──


def _cookie_path() -> str:
    return f"{get_settings().public_api_prefix}/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=_cookie_path(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=_cookie_path(), httponly=True, secure=get_settings().cookie_secure, samesite="strict")


# ── Sessions ──


def issue_session(
    db: Session, user: User, response: Response, *, user_agent: str | None, family_id: str | None = None
) -> schemas.AuthSession:
    """Mint a refresh token (new family unless rotating) + access token. Commits."""
    token, digest = new_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or prefixed_id("fam")(),
            token_hash=digest,
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_ttl_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    db.commit()
    db.refresh(user)
    set_refresh_cookie(response, token)
    access, expires_in = create_access_token(user.id)
    return schemas.AuthSession(access_token=access, expires_in=expires_in, user=to_profile(user))


def rotate(db: Session, presented: str | None, response: Response, *, user_agent: str | None) -> schemas.AuthSession:
    """Exchange a refresh token for a new pair. Reuse of a rotated token revokes its family."""
    unauthenticated = ApiError(401, "UNAUTHENTICATED", "Your session has ended. Please sign in again.")
    if not presented:
        raise unauthenticated
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(presented)))
    if record is None:
        clear_refresh_cookie(response)
        raise unauthenticated
    if record.revoked_at is not None:
        revoked_at = record.revoked_at.replace(tzinfo=record.revoked_at.tzinfo or utcnow().tzinfo)
        if (utcnow() - revoked_at).total_seconds() < REUSE_GRACE_SECONDS:
            # Concurrent refresh (another tab won the race). Keep the cookie: it may already hold the new token.
            raise unauthenticated
        # A token that was already used came back later: someone else may hold it.
        revoke_family(db, record.family_id)
        db.commit()
        log.warning("refresh token reuse detected; revoked family %s for user %s", record.family_id, record.user_id)
        clear_refresh_cookie(response)
        raise unauthenticated
    if record.expires_at.replace(tzinfo=record.expires_at.tzinfo or utcnow().tzinfo) <= utcnow():
        clear_refresh_cookie(response)
        raise unauthenticated

    record.revoked_at = utcnow()
    user = db.get(User, record.user_id)
    return issue_session(db, user, response, user_agent=user_agent, family_id=record.family_id)


def revoke_token(db: Session, presented: str | None) -> None:
    if presented:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(presented), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )


def revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow())
    )


def revoke_all(db: Session, user_id: str) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))
