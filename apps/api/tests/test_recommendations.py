from test_auth import bearer

FEATURES = {
    "face_shape": {"value": "round", "confidence": 0.9},
    "undertone": {"value": "warm", "confidence": 0.8},
    "skin_depth": {"value": "medium", "confidence": 0.75},
    "contrast": {"value": "high", "confidence": 0.8},
}


def test_recommendations_use_estimated_features_and_saved_preferences(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    preferences = {
        "style_goals": ["hair", "palette"],
        "occasions": ["work"],
        "budget": "low",
        "style": "minimal",
        "categories": ["hair"],
    }
    assert client.patch("/v1/me", json={"preferences": preferences}, headers=headers).status_code == 200

    response = client.post("/v1/recommendations", json=FEATURES, headers=headers)
    assert response.status_code == 200
    result = response.json()

    assert result["features"]["face_shape"]["value"] == "round"
    assert result["season"]["value"] == "autumn"
    assert result["season"]["confidence"] <= 0.7
    assert len(result["palette"]) == 5
    categories = {group["category"] for group in result["recommendations"]}
    assert categories == {"hair", "eyewear", "makeup", "outfit_color", "outfit_cut"}
    for group in result["recommendations"]:
        assert 1 <= len(group["items"]) <= 3
        scores = [item["score"] for item in group["items"]]
        assert scores == sorted(scores, reverse=True)
        assert all(0 <= score <= 1 for score in scores)
    assert "not a diagnosis" in result["disclaimer"]


def test_recommendations_rank_budget_and_style_and_are_deterministic(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    low = {"budget": "low", "style": "minimal", "categories": ["hair"], "style_goals": ["hair"], "occasions": ["work"]}
    high = {"budget": "high", "style": "minimal", "categories": ["hair"], "style_goals": ["hair"], "occasions": ["work"]}
    client.patch("/v1/me", json={"preferences": low}, headers=headers)
    low_result = client.post("/v1/recommendations", json=FEATURES, headers=headers).json()
    again = client.post("/v1/recommendations", json=FEATURES, headers=headers).json()
    assert low_result == again

    client.patch("/v1/me", json={"preferences": high}, headers=headers)
    high_result = client.post("/v1/recommendations", json=FEATURES, headers=headers).json()
    low_hair = next(group for group in low_result["recommendations"] if group["category"] == "hair")["items"]
    high_hair = next(group for group in high_result["recommendations"] if group["category"] == "hair")["items"]
    low_side_part = next(item for item in low_hair if item["id"] == "hair.side_part")
    high_side_part = next(item for item in high_hair if item["id"] == "hair.side_part")
    assert low_side_part["within_budget"] is False
    assert high_side_part["within_budget"] is True
    assert round(high_side_part["score"] - low_side_part["score"], 3) == 0.08
    assert all(item["within_budget"] for item in low_hair if item["budget"] == "low")
    assert all(item["within_budget"] for item in high_hair)

    classic = {**high, "style": "classic"}
    client.patch("/v1/me", json={"preferences": classic}, headers=headers)
    classic_result = client.post("/v1/recommendations", json=FEATURES, headers=headers).json()
    classic_hair = next(group for group in classic_result["recommendations"] if group["category"] == "hair")["items"]
    assert classic_hair[0]["id"] == "hair.long_layers"


def test_recommendations_require_auth_and_reject_invalid_estimates(client, signup):
    assert client.post("/v1/recommendations", json=FEATURES).status_code == 401
    _, _, session = signup()
    invalid = {**FEATURES, "face_shape": {"value": "unknown", "confidence": 1.2}}
    response = client.post("/v1/recommendations", json=invalid, headers=bearer(session))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_season_rules_cover_neutral_olive_and_skin_depth_variants(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    cases = (
        ("cool", "deep", "high", "winter"),
        ("cool", "light", "low", "summer"),
        ("warm", "deep", "low", "autumn"),
        ("neutral", "fair", "low", "summer"),
        ("olive", "tan", "medium", "spring"),
    )
    for undertone, skin_depth, contrast, expected in cases:
        features = {
            **FEATURES,
            "undertone": {"value": undertone, "confidence": 0.8},
            "skin_depth": {"value": skin_depth, "confidence": 0.75},
            "contrast": {"value": contrast, "confidence": 0.8},
        }
        response = client.post("/v1/recommendations", json=features, headers=headers)
        assert response.status_code == 200
        assert response.json()["season"]["value"] == expected


def test_low_confidence_features_pull_fit_toward_neutral(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    high_confidence = {
        **FEATURES,
        "face_shape": {"value": "round", "confidence": 1},
    }
    low_confidence = {
        **FEATURES,
        "face_shape": {"value": "round", "confidence": 0},
    }

    high_result = client.post("/v1/recommendations", json=high_confidence, headers=headers).json()
    low_result = client.post("/v1/recommendations", json=low_confidence, headers=headers).json()
    high_hair = next(group for group in high_result["recommendations"] if group["category"] == "hair")["items"]
    low_hair = next(group for group in low_result["recommendations"] if group["category"] == "hair")["items"]
    high_pick = next(item for item in high_hair if item["id"] == "hair.long_layers")
    low_pick = next(item for item in low_hair if item["id"] == "hair.long_layers")
    assert high_pick["score"] > low_pick["score"]
