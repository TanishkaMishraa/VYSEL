from test_auth import bearer


def test_new_profile_has_empty_preferences(client, signup):
    _, _, session = signup()
    me = client.get("/v1/me", headers=bearer(session)).json()
    assert me["preferences"] == {"style_goals": [], "occasions": [], "budget": None, "style": None, "categories": []}
    assert me["onboarding_completed"] is False
    assert me["has_password"] is True and me["auth_providers"] == ["password"]


def test_onboarding_submission_stores_answers_and_completes(client, signup):
    _, _, session = signup()
    answers = {
        "preferences": {
            "style_goals": ["hair", "palette", "special_occasion"],
            "occasions": ["work", "festive"],
            "budget": "mid",
            "style": "classic",
            "categories": ["hair", "makeup"],
        },
        "onboarding_completed": True,
    }
    res = client.patch("/v1/me", json=answers, headers=bearer(session))
    assert res.status_code == 200
    body = res.json()
    assert body["onboarding_completed"] is True
    assert body["preferences"] == answers["preferences"]
    # Persisted: a fresh read returns the same answers.
    assert client.get("/v1/me", headers=bearer(session)).json()["preferences"] == answers["preferences"]


def test_signup_onboarding_login_and_profile_load_flow(client, signup):
    email, password, session = signup()
    headers = bearer(session)
    preferences = {
        "style_goals": ["hair", "palette"],
        "occasions": ["work", "festive"],
        "budget": "mid",
        "style": "classic",
        "categories": ["hair"],
    }

    saved = client.patch(
        "/v1/me",
        json={"preferences": preferences, "onboarding_completed": True},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["onboarding_completed"] is True

    logged_in = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    dashboard_profile = client.get("/v1/me", headers=bearer(logged_in.json()))
    assert dashboard_profile.status_code == 200
    assert dashboard_profile.json()["display_name"] == session["user"]["display_name"]
    assert dashboard_profile.json()["preferences"] == preferences
    assert dashboard_profile.json()["onboarding_completed"] is True


def test_patch_is_a_merge_and_null_clears(client, signup):
    _, _, session = signup()
    h = bearer(session)
    client.patch("/v1/me", json={"preferences": {"budget": "high", "occasions": ["travel"], "style": "bold"}}, headers=h)
    res = client.patch("/v1/me", json={"preferences": {"budget": None}, "display_name": "Tanya M."}, headers=h)
    body = res.json()
    assert body["display_name"] == "Tanya M."
    assert body["preferences"]["budget"] is None  # cleared
    assert body["preferences"]["occasions"] == ["travel"]  # untouched
    assert body["preferences"]["style"] == "bold"  # untouched


def test_invalid_preference_values_are_rejected(client, signup):
    _, _, session = signup()
    for bad in ({"budget": "luxury"}, {"occasions": ["moon-landing"]}, {"unknown_field": 1}):
        res = client.patch("/v1/me", json={"preferences": bad}, headers=bearer(session))
        assert res.status_code == 422, bad
        assert res.json()["code"] == "VALIDATION_ERROR"


def test_duplicate_choices_are_collapsed(client, signup):
    _, _, session = signup()
    res = client.patch("/v1/me", json={"preferences": {"occasions": ["work", "work", "dates"]}}, headers=bearer(session))
    assert res.json()["preferences"]["occasions"] == ["work", "dates"]


def test_delete_account_erases_user(client, signup):
    email, password, session = signup()
    assert client.delete("/v1/me", headers=bearer(session)).status_code == 204
    assert client.get("/v1/me", headers=bearer(session)).status_code == 401
    assert client.post("/v1/auth/login", json={"email": email, "password": password}).status_code == 401
