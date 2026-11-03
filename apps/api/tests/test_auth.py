import re
from datetime import timedelta

from conftest import unique_email

from app.db import SessionLocal, utcnow
from app.models import RefreshToken, User
from app.security import decode_access_token, hash_token


def bearer(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


# ── Registration & login ────────────────────────────────────────────────────


def test_register_returns_session_and_sets_refresh_cookie(client):
    email = unique_email()
    res = client.post("/v1/auth/register", json={"email": email.upper(), "password": "correct-horse-battery", "display_name": "  Tanya "})
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 900
    assert body["user"]["email"] == email  # normalised to lower case
    assert body["user"]["display_name"] == "Tanya"
    assert body["user"]["onboarding_completed"] is False
    assert decode_access_token(body["access_token"]) == body["user"]["id"]

    cookie = res.headers["set-cookie"]
    assert "vysel_refresh=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/v1/auth" in cookie


def test_password_is_hashed_with_argon2id(client, signup):
    email, password, _ = signup()
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).one()
        assert user.password_hash.startswith("$argon2id$")
        assert password not in user.password_hash


def test_duplicate_email_is_409(client, signup):
    email, _, _ = signup()
    res = client.post("/v1/auth/register", json={"email": email, "password": "another-password-1", "display_name": "X"})
    assert res.status_code == 409
    assert res.json()["code"] == "EMAIL_TAKEN"


def test_weak_password_is_rejected(client):
    res = client.post("/v1/auth/register", json={"email": unique_email(), "password": "short", "display_name": "X"})
    assert res.status_code == 422
    assert res.json()["errors"][0]["field"] == "password"


def test_login_success_and_generic_failures(client, signup):
    email, password, _ = signup()
    ok = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == email

    wrong = client.post("/v1/auth/login", json={"email": email, "password": "wrong-password-123"})
    unknown = client.post("/v1/auth/login", json={"email": unique_email(), "password": "whatever-123456"})
    for res in (wrong, unknown):  # identical response: no account enumeration
        assert res.status_code == 401
        assert res.json()["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_me_requires_valid_access_token(client, signup):
    _, _, session = signup()
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    me = client.get("/v1/me", headers=bearer(session))
    assert me.status_code == 200 and me.json()["id"] == session["user"]["id"]


# ── Refresh rotation & reuse detection ─────────────────────────────────────


def test_refresh_rotates_token(client, signup):
    signup()
    first = client.cookies.get("vysel_refresh")
    res = client.post("/v1/auth/refresh")
    assert res.status_code == 200
    second = client.cookies.get("vysel_refresh")
    assert second and second != first


def test_reusing_a_rotated_refresh_token_revokes_the_family(client, signup):
    _, _, session = signup()
    stolen = client.cookies.get("vysel_refresh")
    assert client.post("/v1/auth/refresh").status_code == 200  # legitimate rotation
    current = client.cookies.get("vysel_refresh")

    # Attacker replays the old token after the concurrency grace window.
    with SessionLocal() as db:
        db.query(RefreshToken).filter_by(token_hash=hash_token(stolen)).update({"revoked_at": utcnow() - timedelta(minutes=1)})
        db.commit()
    client.cookies.set("vysel_refresh", stolen, path="/v1/auth")
    assert client.post("/v1/auth/refresh").status_code == 401

    client.cookies.set("vysel_refresh", current, path="/v1/auth")  # legitimate token is now dead too
    assert client.post("/v1/auth/refresh").status_code == 401
    with SessionLocal() as db:
        live = db.query(RefreshToken).filter_by(user_id=session["user"]["id"], revoked_at=None).count()
        assert live == 0


def test_concurrent_refresh_within_grace_does_not_log_the_user_out(client, signup):
    signup()
    old = client.cookies.get("vysel_refresh")
    assert client.post("/v1/auth/refresh").status_code == 200  # tab A wins
    current = client.cookies.get("vysel_refresh")
    client.cookies.set("vysel_refresh", old, path="/v1/auth")
    assert client.post("/v1/auth/refresh").status_code == 401  # tab B loses the race…
    client.cookies.set("vysel_refresh", current, path="/v1/auth")
    assert client.post("/v1/auth/refresh").status_code == 200  # …but the session survives


def test_refresh_without_cookie_is_401(client):
    client.cookies.clear()
    res = client.post("/v1/auth/refresh")
    assert res.status_code == 401 and res.json()["code"] == "UNAUTHENTICATED"


def test_logout_revokes_refresh_token(client, signup):
    signup()
    token = client.cookies.get("vysel_refresh")
    assert client.post("/v1/auth/logout").status_code == 204
    client.cookies.set("vysel_refresh", token, path="/v1/auth")
    assert client.post("/v1/auth/refresh").status_code == 401


# ── Password reset ──────────────────────────────────────────────────────────


def _reset_token_from(outbox) -> str:
    match = re.search(r"/reset-password\?token=([\w\-%]+)", outbox[-1]["text"])
    assert match, outbox[-1]["text"]
    return match.group(1)


def test_password_reset_flow(client, signup, outbox):
    email, old_password, _ = signup()
    other_session_cookie = client.cookies.get("vysel_refresh")

    res = client.post("/v1/auth/password/forgot", json={"email": email})
    assert res.status_code == 202
    assert len(outbox) == 1 and outbox[0]["to"] == email
    token = _reset_token_from(outbox)

    new_password = "brand-new-password-42"
    assert client.post("/v1/auth/password/reset", json={"token": token, "password": new_password}).status_code == 204

    assert client.post("/v1/auth/login", json={"email": email, "password": old_password}).status_code == 401
    assert client.post("/v1/auth/login", json={"email": email, "password": new_password}).status_code == 200

    # Reset signs out existing sessions…
    client.cookies.set("vysel_refresh", other_session_cookie, path="/v1/auth")
    assert client.post("/v1/auth/refresh").status_code == 401
    # …and the link works only once.
    again = client.post("/v1/auth/password/reset", json={"token": token, "password": "yet-another-pass-9"})
    assert again.status_code == 400 and again.json()["code"] == "RESET_TOKEN_INVALID"


def test_forgot_password_does_not_reveal_unknown_emails(client, outbox):
    res = client.post("/v1/auth/password/forgot", json={"email": unique_email()})
    assert res.status_code == 202
    assert outbox == []


def test_requesting_a_new_reset_link_invalidates_the_old_one(client, signup, outbox):
    email, _, _ = signup()
    client.post("/v1/auth/password/forgot", json={"email": email})
    first = _reset_token_from(outbox)
    client.post("/v1/auth/password/forgot", json={"email": email})
    res = client.post("/v1/auth/password/reset", json={"token": first, "password": "some-new-password-1"})
    assert res.status_code == 400
