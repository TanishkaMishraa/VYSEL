from conftest import unique_email

import app.ratelimit as rl


class FakeRedis:
    """Just enough of the redis client for the limiter."""

    def __init__(self):
        self.counts = {}

    def pipeline(self):
        return self

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1

    def expire(self, *_a, **_k):
        pass

    def execute(self):
        return [max(self.counts.values()), True]

    def ttl(self, _key):
        return 42


def test_login_is_rate_limited_per_email(client, monkeypatch):
    settings = rl.get_settings().model_copy(update={"rate_limit_enabled": True})
    monkeypatch.setattr(rl, "get_settings", lambda: settings)
    monkeypatch.setattr(rl, "_client", lambda fake=FakeRedis(): fake)

    email = unique_email()
    codes = [client.post("/v1/auth/login", json={"email": email, "password": "x" * 12}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
    last = client.post("/v1/auth/login", json={"email": email, "password": "x" * 12})
    assert last.json()["code"] == "RATE_LIMITED" and last.headers["retry-after"] == "42"
