"""Password hashing, access tokens and opaque single-use tokens."""

import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings
from app.db import utcnow

# argon2id with the library's current recommended parameters (RFC 9106 low-memory profile).
_hasher = PasswordHasher()
# Verified against when the email doesn't exist, so login takes the same time either way.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: str) -> tuple[str, int]:
    """Short-lived JWT. Returns (token, lifetime_seconds)."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = utcnow()
    claims = {"sub": user_id, "type": "access", "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> str | None:
    """Returns the user id, or None if the token is invalid, expired or not an access token."""
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp", "type"]})
    except jwt.PyJWTError:
        return None
    return claims["sub"] if claims.get("type") == "access" else None


def sign_state(data: dict, ttl_seconds: int) -> str:
    """Tamper-proof, expiring blob (used for the OAuth state cookie)."""
    now = utcnow()
    return jwt.encode(
        {**data, "type": "state", "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}, get_settings().jwt_secret, ALGORITHM
    )


def read_state(token: str) -> dict | None:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return claims if claims.get("type") == "state" else None


def new_opaque_token() -> tuple[str, str]:
    """Random 256-bit token for refresh/reset. Returns (token_for_client, sha256_for_db)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
