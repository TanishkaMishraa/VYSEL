"""Verify PostgreSQL and Redis connectivity for the VYSEL API.

    apps/api/.venv/Scripts/python apps/api/scripts/check_services.py   (Windows)
    apps/api/.venv/bin/python apps/api/scripts/check_services.py       (Linux/macOS)

Reads DATABASE_URL / REDIS_URL from the environment or apps/api/.env.
Checks: connect, server version, write+read+rollback round trip. Exit code 1 on any failure.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import redis
from sqlalchemy import create_engine, text

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env() -> None:
    """Minimal .env loader (no extra dependency); real env vars win."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def redact(url: str) -> str:
    """Hide the password in connection strings before printing."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return url


def check_postgres(url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        version = conn.execute(text("SHOW server_version")).scalar_one()
        db, user = conn.execute(text("SELECT current_database(), current_user")).one()
        print(f"  ✓ PostgreSQL {version} — database '{db}' as '{user}'")
        # Write/read round trip in the auto-begun transaction, then roll back: leaves no trace.
        conn.execute(text("CREATE TEMP TABLE vysel_healthcheck (id text PRIMARY KEY)"))
        token = uuid.uuid4().hex
        conn.execute(text("INSERT INTO vysel_healthcheck VALUES (:t)"), {"t": token})
        if conn.execute(text("SELECT id FROM vysel_healthcheck")).scalar_one() != token:
            raise RuntimeError("read-back value did not match what was written")
        conn.rollback()
        print("  ✓ PostgreSQL write/read round trip")
    engine.dispose()


def check_redis(url: str) -> None:
    client = redis.Redis.from_url(url, socket_connect_timeout=3)
    if not client.ping():
        raise RuntimeError("PING returned false")
    info = client.info("server")
    key = f"vysel:healthcheck:{uuid.uuid4().hex}"
    client.set(key, "ok", ex=10)
    if client.get(key) != b"ok":
        raise RuntimeError("GET did not return the value just SET")
    client.delete(key)
    print(f"  ✓ Redis-compatible server {info.get('redis_version')} — PING, SET/GET round trip")


def main() -> int:
    load_env()
    failures = 0
    checks = (("DATABASE_URL", check_postgres), ("REDIS_URL", check_redis))
    for var, check in checks:
        url = os.environ.get(var)
        print(f"{var} = {redact(url) if url else '(not set)'}")
        if not url:
            print(f"  ✗ {var} is not set — copy apps/api/.env.example to apps/api/.env")
            failures += 1
            continue
        try:
            check(url)
        except Exception as exc:  # report every failure, keep checking the rest
            print(f"  ✗ {type(exc).__name__}: {exc}")
            failures += 1
    print("\nAll services reachable." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
