"""Google sign-in. Network calls are stubbed; ID-token verification runs for real
against a locally generated RSA key standing in for Google's JWKS."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from conftest import unique_email
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.services import google

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:
    def get_signing_key_from_jwt(self, _token):
        return type("K", (), {"key": KEY.public_key()})()


def make_id_token(**overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": get_settings().google_client_id,
        "sub": "google-sub-123",
        "email": "someone@example.com",
        "email_verified": True,
        "name": "Some One",
        "nonce": "n",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **overrides,
    }
    return jwt.encode(claims, KEY, algorithm="RS256")


@pytest.fixture(autouse=True)
def fake_jwks(monkeypatch):
    monkeypatch.setattr(google, "_jwks", lambda: FakeJwks())


# ── ID token verification ──


def test_valid_id_token_is_accepted():
    identity = google.verify_id_token(make_id_token(), nonce="n")
    assert identity.sub == "google-sub-123" and identity.email_verified


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-elses-client"},
        {"iss": "https://evil.example"},
        {"nonce": "replayed"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_bad_id_tokens_are_rejected(overrides):
    with pytest.raises(google.GoogleAuthError):
        google.verify_id_token(make_id_token(**overrides), nonce="n")


def test_token_signed_by_another_key_is_rejected():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {"sub": "x", "aud": get_settings().google_client_id, "iss": "https://accounts.google.com", "nonce": "n"}, other, "RS256"
    )
    with pytest.raises(google.GoogleAuthError):
        google.verify_id_token(forged, nonce="n")


# ── Full redirect flow ──


def _start(client) -> dict:
    res = client.get("/v1/auth/google/start?next=/onboarding", follow_redirects=False)
    assert res.status_code == 302
    q = parse_qs(urlparse(res.headers["location"]).query)
    assert res.headers["location"].startswith("https://accounts.google.com/")
    assert q["code_challenge_method"] == ["S256"] and q["redirect_uri"] == [get_settings().google_redirect_uri]
    return {k: v[0] for k, v in q.items()}


def _callback(client, monkeypatch, params: dict, **claims):
    monkeypatch.setattr(google, "exchange_code", lambda code, verifier: make_id_token(nonce=params["nonce"], **claims))
    return client.get(f"/v1/auth/google/callback?code=abc&state={params['state']}", follow_redirects=False)


def test_google_sign_in_creates_account_and_session(client, monkeypatch):
    email = unique_email()
    res = _callback(client, monkeypatch, _start(client), email=email, sub=f"sub-{email}")
    assert res.status_code == 302
    assert res.headers["location"] == f"{get_settings().web_url}/auth/callback?next=/onboarding"

    session = client.post("/v1/auth/refresh").json()  # the frontend's next call
    assert session["user"]["email"] == email
    assert session["user"]["auth_providers"] == ["google"] and session["user"]["has_password"] is False


def test_google_links_existing_password_account(client, monkeypatch, signup):
    email, password, _ = signup()
    _callback(client, monkeypatch, _start(client), email=email, sub=f"sub-{email}")
    user = client.post("/v1/auth/refresh").json()["user"]
    assert user["auth_providers"] == ["google", "password"]
    assert client.post("/v1/auth/login", json={"email": email, "password": password}).status_code == 200


def test_state_mismatch_is_refused(client, monkeypatch):
    params = _start(client)
    params["state"] = "forged-state"
    res = _callback(client, monkeypatch, params)
    assert res.headers["location"].endswith("/login?error=google_failed")


def test_unverified_google_email_is_refused(client, monkeypatch):
    res = _callback(client, monkeypatch, _start(client), email=unique_email(), email_verified=False)
    assert res.headers["location"].endswith("/login?error=google_unverified")


def test_open_redirect_in_next_is_neutralised(client):
    res = client.get("/v1/auth/google/start?next=//evil.example", follow_redirects=False)
    assert res.status_code == 302  # cookie stores the safe fallback; covered by _safe_next below
    from app.api.auth import _safe_next

    assert _safe_next("//evil.example") == "/profile"
    assert _safe_next("https://evil.example") == "/profile"
    assert _safe_next("/onboarding") == "/onboarding"


def test_providers_endpoint(client):
    assert client.get("/v1/auth/providers").json() == {"password": True, "google": True}
