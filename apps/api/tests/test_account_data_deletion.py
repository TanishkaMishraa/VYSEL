from datetime import timedelta
from secrets import token_hex
from types import SimpleNamespace

from test_reports import bearer, create_report

from app.db import SessionLocal, utcnow
from app.models import (
    FaceScan,
    ImageUpload,
    OAuthAccount,
    PasswordResetToken,
    RecommendationFeedback,
    RecommendationReport,
    RefreshToken,
    SavedTryOnLook,
    User,
    UserPreferences,
)
from app.services.image_storage import store_image


def test_account_deletion_removes_database_rows_and_private_files(client, signup, monkeypatch, tmp_path):
    email, password, session = signup()
    headers = bearer(session)
    user_id = session["user"]["id"]
    monkeypatch.setattr("app.api.me.get_settings", lambda: SimpleNamespace(selfie_storage_dir=tmp_path))

    report = create_report(client, headers)
    share = client.post(f"/v1/reports/{report['id']}/share", headers=headers)
    assert share.status_code == 200
    share_token = share.json()["share_url"].rsplit("/", 1)[-1]
    first_recommendation = report["report_data"]["recommendations"][0]["items"][0]
    assert (
        client.put(
            f"/v1/reports/{report['id']}/feedback",
            headers=headers,
            json={"recommendation_id": first_recommendation["id"], "helpful": True},
        ).status_code
        == 200
    )
    look = {
        "name": "Office look",
        "occasion": "office",
        "look": {
            "lips": {"enabled": True, "shade_id": "lip.rose", "shade_name": "Rose", "hex": "#B85F70", "intensity": 0.6},
            "blush": {"enabled": False, "shade_id": "blush.soft", "shade_name": "Soft pink", "hex": "#D98A92", "intensity": 0.4},
            "liner": {
                "enabled": False,
                "shade_id": "liner.black",
                "shade_name": "Black",
                "hex": "#1A1416",
                "intensity": 0.8,
                "wing": False,
            },
        },
    }
    assert client.post("/v1/saved-looks", headers=headers, json=look).status_code == 201

    storage_key = f"{token_hex(16)}.jpg"
    image_path = store_image(tmp_path, storage_key, b"private selfie bytes")
    with SessionLocal() as db:
        image = ImageUpload(
            user_id=user_id,
            storage_key=storage_key,
            filename="selfie.jpg",
            content_type="image/jpeg",
            size_bytes=20,
            width=256,
            height=256,
            blur_variance=40,
            mean_brightness=100,
            validation_results={},
            consent_policy_version="test",
            retention="ephemeral",
            expires_at=utcnow() + timedelta(hours=24),
        )
        db.add(image)
        db.flush()
        db.add(
            FaceScan(
                user_id=user_id,
                image_id=image.id,
                status="succeeded",
                face_count=1,
                detection_confidence=0.9,
                model_version="test",
                result={"biometric_landmarks": [1]},
                expires_at=utcnow() + timedelta(hours=24),
            )
        )
        db.add(OAuthAccount(user_id=user_id, provider="google", provider_user_id=f"google-{user_id}"))
        db.add(
            PasswordResetToken(
                user_id=user_id,
                token_hash=token_hex(32),
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        db.commit()

    deleted = client.delete("/v1/me", headers=headers)
    assert deleted.status_code == 204
    assert not image_path.exists()
    assert client.get("/v1/me", headers=headers).status_code == 401
    assert client.post("/v1/auth/login", json={"email": email, "password": password}).status_code == 401
    assert client.get(f"/v1/reports/shared/{share_token}").status_code == 404

    with SessionLocal() as db:
        for model in (
            User,
            UserPreferences,
            OAuthAccount,
            RefreshToken,
            PasswordResetToken,
            ImageUpload,
            FaceScan,
            RecommendationReport,
            RecommendationFeedback,
            SavedTryOnLook,
        ):
            filter_field = "id" if model is User else "user_id"
            filter_value = user_id
            assert db.query(model).filter(getattr(model, filter_field) == filter_value).count() == 0, model.__tablename__


def test_account_deletion_keeps_account_if_private_file_cannot_be_removed(client, signup, monkeypatch, tmp_path):
    _, _, session = signup()
    headers = bearer(session)
    user_id = session["user"]["id"]
    with SessionLocal() as db:
        db.add(
            ImageUpload(
                user_id=user_id,
                storage_key=f"{token_hex(16)}.jpg",
                filename="selfie.jpg",
                content_type="image/jpeg",
                size_bytes=20,
                width=256,
                height=256,
                blur_variance=40,
                mean_brightness=100,
                validation_results={},
                consent_policy_version="test",
                retention="ephemeral",
                expires_at=utcnow() + timedelta(hours=24),
            )
        )
        db.commit()

    monkeypatch.setattr("app.api.me.get_settings", lambda: SimpleNamespace(selfie_storage_dir=tmp_path))
    monkeypatch.setattr("app.api.me.remove_image", lambda *_args: (_ for _ in ()).throw(PermissionError("denied")))

    response = client.delete("/v1/me", headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "DATA_DELETION_INCOMPLETE"
    assert client.get("/v1/me", headers=headers).status_code == 200
