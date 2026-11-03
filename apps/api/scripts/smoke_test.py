"""End-to-end smoke test against running services.

Verifies: API up → health (DB, Redis, queue) → hello job queued → worker executes →
status persisted in PostgreSQL and readable via the API (and via the web proxy, if given).

    python apps/api/scripts/smoke_test.py [--api http://localhost:8000] [--web http://localhost:3000] [--timeout 60]
Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx


def wait_for(url: str, timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code < 500:
                print(f"  ✓ {label} responding ({r.status_code})")
                return
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        time.sleep(1)
    raise RuntimeError(f"{label} not ready after {timeout:.0f}s ({last})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", default=None, help="also check the Next.js app and its /api proxy")
    ap.add_argument("--timeout", type=float, default=60)
    args = ap.parse_args()

    try:
        print("API")
        wait_for(f"{args.api}/v1/health", args.timeout, "FastAPI")
        health = httpx.get(f"{args.api}/v1/health", timeout=5)
        body = health.json()
        if health.status_code != 200:
            raise RuntimeError(f"health is {body['status']}: {body['checks']}")
        print(f"  ✓ health ok — {body['checks']} (v{body['version']})")

        print("Worker")
        created = httpx.post(f"{args.api}/v1/jobs/hello", json={"name": "VYSEL"}, timeout=5)
        if created.status_code != 202:
            raise RuntimeError(f"enqueue failed: HTTP {created.status_code} {created.text[:200]}")
        job_id = created.json()["id"]
        print(f"  ✓ job {job_id} queued")

        deadline = time.monotonic() + args.timeout
        seen = []
        while time.monotonic() < deadline:
            job = httpx.get(f"{args.api}/v1/jobs/{job_id}", timeout=5).json()
            if not seen or seen[-1] != job["status"]:
                seen.append(job["status"])
            if job["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"job still {seen[-1]} after {args.timeout:.0f}s — is the Celery worker running?")
        if job["status"] != "succeeded":
            raise RuntimeError(f"job failed: {job['error']}")
        print(f"  ✓ status transitions: {' → '.join(seen)}")
        print(f"  ✓ result from worker '{job['result']['worker']}': {job['result']['message']}")

        if args.web:
            print("Web")
            wait_for(args.web, args.timeout * 2, "Next.js")  # first dev compile is slow
            proxied = httpx.get(f"{args.web}/api/v1/jobs/{job_id}", timeout=30)
            if proxied.status_code != 200 or proxied.json()["status"] != "succeeded":
                raise RuntimeError(f"web proxy check failed: HTTP {proxied.status_code}")
            print("  ✓ /api/v1 proxy reaches FastAPI (same-origin)")
    except Exception as exc:
        print(f"  ✗ {exc}")
        print("\nSmoke test FAILED.")
        return 1

    print("\nSmoke test passed — all services working together.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
