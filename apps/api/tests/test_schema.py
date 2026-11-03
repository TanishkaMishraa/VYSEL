"""Relationships between users, profiles, analyses, reports, recommendations, feedback and saved looks."""

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AnalysisResult, Recommendation, RecommendationFeedback, RecommendationReport, SavedTryOnLook, UserProfile
from tests.test_reports import FEATURES, bearer, create_report
from tests.test_saved_looks import LOOK


def count(db, model, **where) -> int:
    return db.scalar(select(func.count()).select_from(model).filter_by(**where))


def test_report_records_its_analysis_recommendations_and_profile_link(client, signup):
    _, _, session = signup()
    report = create_report(client, bearer(session))
    user_id = session["user"]["id"]

    with SessionLocal() as db:
        stored = db.get(RecommendationReport, report["id"])
        analysis = stored.analysis
        assert analysis.user_id == user_id
        assert analysis.source == "manual" and analysis.scan_id is None
        assert analysis.features == FEATURES
        assert db.get(UserProfile, user_id).latest_analysis_id == analysis.id

        expected = [
            (g["category"], rank, i["id"]) for g in report["report_data"]["recommendations"] for rank, i in enumerate(g["items"], 1)
        ]
        assert sorted((r.category, r.rank, r.item_key) for r in stored.recommendations) == sorted(expected)


def test_report_rejects_a_scan_the_user_does_not_own(client, signup):
    _, _, session = signup()
    response = client.post("/v1/reports", json={"features": FEATURES, "scan_id": "scn_missing"}, headers=bearer(session))
    assert response.status_code == 404


def test_deleting_a_report_cascades_to_recommendations_and_feedback_but_keeps_the_analysis(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    report = create_report(client, headers)
    item = report["report_data"]["recommendations"][0]["items"][0]["id"]
    assert (
        client.put(f"/v1/reports/{report['id']}/feedback", json={"recommendation_id": item, "helpful": True}, headers=headers).status_code
        == 200
    )

    with SessionLocal() as db:
        analysis_id = db.get(RecommendationReport, report["id"]).analysis_id
    assert client.delete(f"/v1/reports/{report['id']}", headers=headers).status_code == 204

    with SessionLocal() as db:
        assert count(db, Recommendation, report_id=report["id"]) == 0
        assert count(db, RecommendationFeedback, report_id=report["id"]) == 0
        assert db.get(AnalysisResult, analysis_id) is not None


def test_deleting_the_account_erases_every_owned_row(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    user_id = session["user"]["id"]
    report = create_report(client, headers)
    item = report["report_data"]["recommendations"][0]["items"][0]["id"]
    client.put(f"/v1/reports/{report['id']}/feedback", json={"recommendation_id": item, "helpful": False}, headers=headers)
    assert client.post("/v1/saved-looks", json={"name": "Office", "occasion": "party", "look": LOOK}, headers=headers).status_code == 201

    assert client.delete("/v1/me", headers=headers).status_code == 204

    with SessionLocal() as db:
        assert db.get(UserProfile, user_id) is None
        for model in (AnalysisResult, RecommendationReport, RecommendationFeedback, SavedTryOnLook):
            assert count(db, model, user_id=user_id) == 0, model.__name__
        assert count(db, Recommendation, report_id=report["id"]) == 0
