"""Google sign-in: OAuth 2.0 authorization code flow with PKCE, state and nonce.

The browser never sees Google tokens. The callback exchanges the code server-side,
verifies the ID token's signature against Google's JWKS, then issues our own session.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt

from app.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — a URL, not a secret
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleAuthError(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


@dataclass(frozen=True)
class AuthRequest:
    url: str
    state: str
    code_verifier: str
    nonce: str


def build_auth_request() -> AuthRequest:
    settings = get_settings()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return AuthRequest(url=f"{AUTH_URL}?{urlencode(params)}", state=state, code_verifier=code_verifier, nonce=nonce)


@lru_cache
def _jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(JWKS_URL, cache_keys=True)


def exchange_code(code: str, code_verifier: str) -> str:
    """Swap the authorization code for an ID token (server-to-server)."""
    settings = get_settings()
    try:
        res = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise GoogleAuthError(f"token endpoint unreachable: {exc}") from exc
    if res.status_code != 200 or "id_token" not in res.json():
        raise GoogleAuthError(f"token exchange failed: HTTP {res.status_code}")
    return res.json()["id_token"]


def verify_id_token(id_token: str, nonce: str) -> GoogleIdentity:
    try:
        key = _jwks().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=get_settings().google_client_id, issuer=ISSUERS)
    except jwt.PyJWTError as exc:
        raise GoogleAuthError(f"invalid ID token: {exc}") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleAuthError("nonce mismatch")
    if not claims.get("email"):
        raise GoogleAuthError("no email in ID token")
    return GoogleIdentity(
        sub=claims["sub"],
        email=claims["email"],
        email_verified=bool(claims.get("email_verified")),
        name=(claims.get("name") or claims["email"].split("@")[0])[:50],
    )
