from app.db import SessionLocal
from app.models import RecommendationFeedback, RecommendationReport
from app.security import hash_token

FEATURES = {
    "face_shape": {"value": "oval", "confidence": 0.8},
    "undertone": {"value": "neutral", "confidence": 0.7},
    "skin_depth": {"value": "medium", "confidence": 0.75},
    "contrast": {"value": "medium", "confidence": 0.6},
}


def bearer(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def create_report(client, headers):
    response = client.post("/v1/reports", json={"features": FEATURES}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_report_is_private_and_account_owned(client, signup):
    _, _, first_session = signup()
    _, _, other_session = signup()
    headers = bearer(first_session)
    report = create_report(client, headers)

    assert report["share_enabled"] is False
    assert report["report_data"]["features"]["face_shape"]["value"] == "oval"
    assert client.get("/v1/reports", headers=headers).json()[0]["id"] == report["id"]
    assert client.get(f"/v1/reports/{report['id']}", headers=bearer(other_session)).status_code == 404
    assert client.get("/v1/reports").status_code == 401


def test_share_link_is_explicit_revocable_and_contains_no_identity(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    report = create_report(client, headers)

    public = client.get(f"/v1/reports/shared/{'x' * 43}")
    assert public.status_code == 404
    link = client.post(f"/v1/reports/{report['id']}/share", headers=headers)
    assert link.status_code == 200
    share_url = link.json()["share_url"]
    token = share_url.rsplit("/", 1)[-1]
    assert token and token not in str(client.get(f"/v1/reports/{report['id']}", headers=headers).json())

    shared = client.get(f"/v1/reports/shared/{token}")
    assert shared.status_code == 200
    assert "email" not in shared.json()
    assert "display_name" not in shared.json()
    with SessionLocal() as db:
        stored = db.get(RecommendationReport, report["id"])
        assert stored is not None
        assert stored.share_token_hash == hash_token(token)
        assert token not in stored.share_token_hash

    assert client.delete(f"/v1/reports/{report['id']}/share", headers=headers).status_code == 204
    assert client.get(f"/v1/reports/shared/{token}").status_code == 404


def test_feedback_is_saved_updated_and_limited_to_report_recommendations(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    report = create_report(client, headers)
    item = report["report_data"]["recommendations"][0]["items"][0]
    path = f"/v1/reports/{report['id']}/feedback"

    positive = client.put(path, headers=headers, json={"recommendation_id": item["id"], "helpful": True})
    assert positive.status_code == 200
    assert positive.json()["helpful"] is True
    negative = client.put(path, headers=headers, json={"recommendation_id": item["id"], "helpful": False})
    assert negative.status_code == 200
    assert negative.json()["helpful"] is False
    persisted = client.get(f"/v1/reports/{report['id']}", headers=headers)
    saved_feedback = persisted.json()["feedback"]
    assert len(saved_feedback) == 1
    assert saved_feedback[0]["recommendation_id"] == item["id"]
    assert saved_feedback[0]["helpful"] is False

    invalid = client.put(path, headers=headers, json={"recommendation_id": "not-in-report", "helpful": True})
    assert invalid.status_code == 404
    assert client.put(path, json={"recommendation_id": item["id"], "helpful": True}).status_code == 401


def test_deleting_report_revokes_share_and_cascades_feedback(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    report = create_report(client, headers)
    item = report["report_data"]["recommendations"][0]["items"][0]
    share = client.post(f"/v1/reports/{report['id']}/share", headers=headers).json()
    token = share["share_url"].rsplit("/", 1)[-1]
    assert (
        client.put(
            f"/v1/reports/{report['id']}/feedback",
            headers=headers,
            json={"recommendation_id": item["id"], "helpful": True},
        ).status_code
        == 200
    )

    assert client.delete(f"/v1/reports/{report['id']}", headers=headers).status_code == 204
    assert client.get(f"/v1/reports/{report['id']}", headers=headers).status_code == 404
    assert client.get(f"/v1/reports/shared/{token}").status_code == 404
    with SessionLocal() as db:
        assert db.query(RecommendationFeedback).filter_by(report_id=report["id"]).count() == 0
