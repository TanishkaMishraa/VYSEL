import app.api.health as health


def test_health_ok_when_dependencies_up(client, monkeypatch):
    monkeypatch.setattr(health, "_redis", lambda _url: "ok")
    res = client.get("/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "cache": "ok", "queue": "ok"}
    assert body["version"]


def test_health_503_when_a_dependency_is_down(client, monkeypatch):
    monkeypatch.setattr(health, "_redis", lambda _url: "down")
    res = client.get("/v1/health")
    assert res.status_code == 503
    assert res.json()["status"] == "down"
    assert res.json()["checks"]["cache"] == "down"
