from test_reports import FEATURES, bearer, create_report

from app.services.product_catalog import PRODUCTS, _color_distance


def test_product_matches_are_attribute_relevant_and_budget_filtered(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    assert client.patch("/v1/me", headers=headers, json={"preferences": {"budget": "low"}}).status_code == 200
    report = create_report(client, headers)

    response = client.get(f"/v1/reports/{report['id']}/products", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "INR"
    assert data["budget_filter"] == "low"
    assert "may change" in data["price_disclaimer"]

    items = {item["id"]: (group["category"], item) for group in report["report_data"]["recommendations"] for item in group["items"]}
    catalog = {product.id: product for product in PRODUCTS}
    for group in data["matches"]:
        category, recommendation = items[group["recommendation_id"]]
        assert group["category"] == category
        for matched in group["products"]:
            product = catalog[matched["id"]]
            assert matched["price_inr"] <= 500
            assert matched["listing_url"].startswith("https://")
            assert 0 <= matched["match_score"] <= 1
            if category == "makeup":
                kind = recommendation["id"].split(".")[1]
                assert product.category == "makeup"
                assert kind in product.tags
                assert _color_distance(recommendation["color_hex"], product.color_hex) <= 145
            elif category == "outfit_color":
                assert product.category == "outfit_color"
                assert _color_distance(recommendation["color_hex"], product.color_hex) <= 110
            elif category == "outfit_cut":
                assert f"cut.{recommendation['id'].rsplit('.', 1)[1]}" in product.tags

    assert any(group["products"] for group in data["matches"])

    all_budget = client.get(f"/v1/reports/{report['id']}/products?budget=all", headers=headers)
    assert all_budget.status_code == 200
    assert all_budget.json()["budget_filter"] == "all"
    assert client.get(f"/v1/reports/{report['id']}/products?budget=invalid", headers=headers).status_code == 422


def test_product_matches_are_private_to_the_report_owner(client, signup):
    _, _, session = signup()
    _, _, other_session = signup()
    report = create_report(client, bearer(session))

    response = client.get(f"/v1/reports/{report['id']}/products", headers=bearer(other_session))
    assert response.status_code == 404


def test_price_filter_uses_catalogue_price_tiers(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    features = {**FEATURES, "face_shape": {"value": "round", "confidence": 0.9}}
    report_response = client.post("/v1/reports", headers=headers, json={"features": features})
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    mid = client.get(f"/v1/reports/{report_id}/products?budget=mid", headers=headers).json()
    high = client.get(f"/v1/reports/{report_id}/products?budget=high", headers=headers).json()
    long_layers_mid = next(match for match in mid["matches"] if match["recommendation_id"] == "hair.long_layers")
    long_layers_high = next(match for match in high["matches"] if match["recommendation_id"] == "hair.long_layers")
    assert long_layers_mid["products"] == []
    assert long_layers_high["products"][0]["id"] == "philips-bhb862-curler"
    assert long_layers_high["products"][0]["price_inr"] > 1500


def test_history_lists_reports_in_reverse_chronological_order(client, signup):
    _, _, session = signup()
    headers = bearer(session)
    older = create_report(client, headers)
    newer = create_report(client, headers)

    history = client.get("/v1/reports", headers=headers)
    assert history.status_code == 200
    ids = [item["id"] for item in history.json()]
    assert ids.index(newer["id"]) < ids.index(older["id"])
    assert all(item["recommendation_count"] > 0 for item in history.json())
