"""Authentication endpoints: password, sessions, password reset, Google sign-in."""

import logging
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import email as email_templates
from app import schemas
from app.config import get_settings
from app.db import get_db, utcnow
from app.errors import ApiError
from app.models import OAuthAccount, PasswordResetToken
from app.ratelimit import client_ip, enforce
from app.security import hash_password, hash_token, new_opaque_token, password_needs_rehash, read_state, sign_state, verify_password
from app.services import auth as sessions
from app.services import google
from app.tasks import send_email

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

OAUTH_COOKIE = "vysel_oauth"
INVALID_CREDENTIALS = ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")


def _ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


# ── Password accounts ───────────────────────────────────────────────────────


@router.post("/register", status_code=201, response_model=schemas.AuthSession)
def register(body: schemas.RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce("register", client_ip(request), limit=10, window_seconds=3600)
    if sessions.get_user_by_email(db, body.email):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = sessions.create_user(db, email=body.email, display_name=body.display_name, password=body.password)
    return sessions.issue_session(db, user, response, user_agent=_ua(request))


@router.post("/login", response_model=schemas.AuthSession)
def login(body: schemas.LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce("login-ip", client_ip(request), limit=30, window_seconds=600)
    enforce("login-email", sessions.normalize_email(body.email), limit=10, window_seconds=900)
    user = sessions.get_user_by_email(db, body.email)
    # verify_password always runs (against a dummy hash if needed): equal timing either way.
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise INVALID_CREDENTIALS
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    return sessions.issue_session(db, user, response, user_agent=_ua(request))


@router.post("/refresh", response_model=schemas.AuthSession)
def refresh(request: Request, response: Response, vysel_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    return sessions.rotate(db, vysel_refresh, response, user_agent=_ua(request))


@router.post("/logout", status_code=204)
def logout(response: Response, vysel_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    sessions.revoke_token(db, vysel_refresh)
    db.commit()
    sessions.clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/providers", response_model=schemas.Providers)
def providers():
    return schemas.Providers(google=get_settings().google_enabled)


# ── Password reset ──────────────────────────────────────────────────────────


@router.post("/password/forgot", status_code=202)
def forgot_password(body: schemas.ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Always 202 with the same body, whether or not the account exists (no enumeration)."""
    settings = get_settings()
    enforce("forgot-ip", client_ip(request), limit=10, window_seconds=900)
    enforce("forgot-email", sessions.normalize_email(body.email), limit=3, window_seconds=3600)
    user = sessions.get_user_by_email(db, body.email)
    if user is not None:
        # One live link at a time: older unused links stop working.
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=utcnow())
        )
        token, digest = new_opaque_token()
        db.add(
            PasswordResetToken(
                user_id=user.id, token_hash=digest, expires_at=utcnow() + timedelta(minutes=settings.password_reset_ttl_minutes)
            )
        )
        db.commit()
        link = f"{settings.web_url}/reset-password?token={quote(token)}"
        subject, text = email_templates.password_reset(user.email, user.display_name, link, settings.password_reset_ttl_minutes)
        try:
            send_email.delay(user.email, subject, text)
        except Exception:
            log.exception("could not queue password reset email")  # still 202: don't reveal anything
    return {"detail": "If an account exists for that email, a reset link is on its way."}


@router.post("/password/reset", status_code=204)
def reset_password(body: schemas.ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    enforce("reset-ip", client_ip(request), limit=20, window_seconds=900)
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    now = utcnow()
    if record is None or record.used_at is not None or record.expires_at.replace(tzinfo=record.expires_at.tzinfo or now.tzinfo) <= now:
        raise ApiError(400, "RESET_TOKEN_INVALID", "This reset link is invalid or has expired. Request a new one.")
    record.used_at = now
    user = sessions.get_user_by_id(db, record.user_id)
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # they proved control of the inbox
    sessions.revoke_all(db, user.id)  # sign out everywhere: the old password may be compromised
    db.commit()
    return Response(status_code=204)


# ── Google sign-in ──────────────────────────────────────────────────────────


def _safe_next(path: str | None) -> str:
    """Only same-site relative paths, so `next` can't become an open redirect."""
    return path if path and path.startswith("/") and not path.startswith("//") and "\\" not in path else "/profile"


def _oauth_cookie_path() -> str:
    return f"{get_settings().public_api_prefix}/auth/google"


def _login_error(reason: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().web_url}/login?error={reason}", status_code=302)


@router.get("/google/start")
def google_start(next: str | None = None):
    settings = get_settings()
    if not settings.google_enabled:
        raise ApiError(404, "NOT_FOUND", "Google sign-in is not configured.")
    req = google.build_auth_request()
    response = RedirectResponse(req.url, status_code=302)
    response.set_cookie(
        OAUTH_COOKIE,
        sign_state({"state": req.state, "verifier": req.code_verifier, "nonce": req.nonce, "next": _safe_next(next)}, ttl_seconds=600),
        max_age=600,
        path=_oauth_cookie_path(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # must survive the top-level redirect back from Google
    )
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    vysel_oauth: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not get_settings().google_enabled:
        return _login_error("google_unavailable")
    saved = read_state(vysel_oauth) if vysel_oauth else None
    if error or not code or not state or saved is None or saved.get("state") != state:
        return _login_error("google_cancelled" if error else "google_failed")

    try:
        identity = google.verify_id_token(google.exchange_code(code, saved["verifier"]), saved["nonce"])
    except google.GoogleAuthError as exc:
        log.warning("google sign-in failed: %s", exc)
        return _login_error("google_failed")
    if not identity.email_verified:
        return _login_error("google_unverified")

    link = db.scalar(select(OAuthAccount).where(OAuthAccount.provider == "google", OAuthAccount.provider_user_id == identity.sub))
    if link:
        user = link.user
    else:
        # Link to an existing account only because Google verified the address.
        user = sessions.get_user_by_email(db, identity.email) or sessions.create_user(
            db, email=identity.email, display_name=identity.name, password=None, email_verified=True
        )
        user.email_verified = True
        db.add(OAuthAccount(user_id=user.id, provider="google", provider_user_id=identity.sub))

    response = RedirectResponse(f"{get_settings().web_url}/auth/callback?next={quote(saved['next'])}", status_code=302)
    sessions.issue_session(db, user, response, user_agent=_ua(request))
    response.delete_cookie(OAUTH_COOKIE, path=_oauth_cookie_path())
    return response
