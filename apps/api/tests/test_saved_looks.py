from app.db import SessionLocal
from app.models import SavedTryOnLook

LOOK = {
    "lips": {"enabled": True, "shade_id": "makeup.lip.0", "shade_name": "Soft rose", "hex": "#B85F70", "intensity": 0.6},
    "blush": {"enabled": False, "shade_id": "starter.blush.d98a92", "shade_name": "Soft pink", "hex": "#D98A92", "intensity": 0.5},
    "liner": {
        "enabled": True,
        "shade_id": "starter.liner.1a1416",
        "shade_name": "Black",
        "hex": "#1A1416",
        "intensity": 0.7,
        "wing": True,
    },
}


def bearer(session: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_saved_looks_are_private_filterable_and_reloadable(client, signup):
    _, _, owner_session = signup()
    _, _, other_session = signup()
    headers = bearer(owner_session)

    created = client.post(
        "/v1/saved-looks",
        headers=headers,
        json={"name": "  Evening rose  ", "occasion": "party", "look": LOOK},
    )
    assert created.status_code == 201, created.text
    saved = created.json()
    assert saved["name"] == "Evening rose"
    assert saved["occasion"] == "party"
    assert saved["look"] == LOOK

    assert client.get("/v1/saved-looks").status_code == 401
    assert client.get("/v1/saved-looks", headers=headers).json() == [saved]
    assert client.get("/v1/saved-looks?occasion=party", headers=headers).json() == [saved]
    assert client.get("/v1/saved-looks?occasion=office", headers=headers).json() == []
    assert client.get(f"/v1/saved-looks/{saved['id']}", headers=bearer(other_session)).status_code == 404

    with SessionLocal() as db:
        persisted = db.get(SavedTryOnLook, saved["id"])
        assert persisted is not None
        assert persisted.user_id == owner_session["user"]["id"]
        assert persisted.look_data == LOOK

    assert client.delete(f"/v1/saved-looks/{saved['id']}", headers=headers).status_code == 204
    assert client.get(f"/v1/saved-looks/{saved['id']}", headers=headers).status_code == 404


def test_saved_look_validation_rejects_bad_occasion_color_and_intensity(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    invalid_requests = [
        {"name": "Look", "occasion": "vacation", "look": LOOK},
        {"name": "Look", "occasion": "office", "look": {**LOOK, "lips": {**LOOK["lips"], "hex": "url(unsafe)"}}},
        {"name": "Look", "occasion": "wedding", "look": {**LOOK, "blush": {**LOOK["blush"], "intensity": 1.1}}},
        {"name": "   ", "occasion": "college", "look": LOOK},
    ]
    for body in invalid_requests:
        assert client.post("/v1/saved-looks", headers=headers, json=body).status_code == 422


def test_saved_look_delete_is_owner_scoped(client, signup):
    _, _, owner_session = signup()
    _, _, other_session = signup()
    created = client.post(
        "/v1/saved-looks",
        headers=bearer(owner_session),
        json={"name": "Office", "occasion": "office", "look": LOOK},
    )
    look_id = created.json()["id"]

    assert client.delete(f"/v1/saved-looks/{look_id}", headers=bearer(other_session)).status_code == 404
    assert client.delete(f"/v1/saved-looks/{look_id}", headers=bearer(owner_session)).status_code == 204
