from datetime import timedelta

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.models import FaceScan, ImageUpload

FEATURES = {
    "face_shape": {"value": "oval", "confidence": 0.8},
    "undertone": {"value": "neutral", "confidence": 0.7},
    "skin_depth": {"value": "medium", "confidence": 0.75},
    "contrast": {"value": "medium", "confidence": 0.6},
}

def bearer(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_admin_overview_requires_allowlisted_account_and_reports_metrics(client, signup, monkeypatch):
    email, _, admin_session = signup()
    _, _, regular_session = signup()
    monkeypatch.setenv("ADMIN_EMAILS", email)
    get_settings.cache_clear()

    try:
        assert client.get("/v1/admin/overview").status_code == 401
        assert client.get("/v1/admin/overview", headers=bearer(regular_session)).status_code == 403
        profile = client.get("/v1/me", headers=bearer(admin_session))
        assert profile.status_code == 200
        assert profile.json()["is_admin"] is True
        baseline = client.get("/v1/admin/overview", headers=bearer(admin_session)).json()

        with SessionLocal() as db:
            image = ImageUpload(
                user_id=admin_session["user"]["id"],
                storage_key="a" * 64,
                filename="selfie.jpg",
                content_type="image/jpeg",
                size_bytes=1024,
                width=512,
                height=512,
                blur_variance=0,
                mean_brightness=100,
                validation_results={"blur": {"passed": False}},
                consent_policy_version="test",
                expires_at=utcnow() + timedelta(days=1),
            )
            db.add(image)
            db.flush()
            db.add(
                FaceScan(
                    user_id=admin_session["user"]["id"],
                    image_id=image.id,
                    status="failed",
                    error_code="LOW_QUALITY",
                    face_count=0,
                    model_version="test-model",
                    result={"warnings": [{"code": "BLUR"}]},
                    expires_at=image.expires_at,
                )
            )
            db.commit()

        response = client.get("/v1/admin/overview", headers=bearer(admin_session))
        assert response.status_code == 200, response.text
        overview = response.json()
        assert overview["registered_users"] == baseline["registered_users"]
        assert email in {user["email"] for user in overview["recent_users"]}
        assert overview["scans"]["total"] == baseline["scans"]["total"] + 1
        assert overview["scans"]["failed"] == baseline["scans"]["failed"] + 1
        assert overview["scans"]["model_versions"]["test-model"]["failed"] == 1
        assert any(failure["category"] == "LOW_QUALITY" for failure in overview["system_failures"])
        assert any(flag["quality_flags"] == ["blur"] for flag in overview["flagged_images"])
        assert any(flag["warning_codes"] == ["BLUR"] for flag in overview["flagged_images"])
        assert overview["model_evaluation"]["status"] == "not_available"
        assert overview["model_evaluation"]["accuracy"] is None
        assert overview["model_evaluation"]["sample_count"] == 0

        report_response = client.post("/v1/reports", json={"features": FEATURES}, headers=bearer(admin_session))
        assert report_response.status_code == 201
        report = report_response.json()
        item = report["report_data"]["recommendations"][0]["items"][0]
        vote = client.put(
            f"/v1/reports/{report['id']}/feedback",
            headers=bearer(admin_session),
            json={"recommendation_id": item["id"], "helpful": True},
        )
        assert vote.status_code == 200

        updated = client.get("/v1/admin/overview", headers=bearer(admin_session)).json()
        assert updated["analyses"] == baseline["analyses"] + 1
        assert updated["feedback_total"] == baseline["feedback_total"] + 1
        assert sum(metric["helpful"] for metric in updated["feedback"]) == sum(metric["helpful"] for metric in baseline["feedback"]) + 1
        assert all("image_bytes" not in str(flag) for flag in updated["flagged_images"])
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
