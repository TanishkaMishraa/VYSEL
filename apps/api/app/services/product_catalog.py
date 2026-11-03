"""Curated India-focused product listings and attribute matching."""

from dataclasses import dataclass
from urllib.parse import quote_plus

from app import schemas


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    brand: str
    retailer: str
    search_term: str
    price_inr: int
    category: str
    tags: frozenset[str]
    color_hex: str | None = None
    shade_name: str | None = None

    @property
    def budget(self) -> schemas.Budget:
        if self.price_inr <= 500:
            return "low"
        if self.price_inr <= 1500:
            return "mid"
        return "high"

    @property
    def listing_url(self) -> str:
        query = quote_plus(self.search_term)
        if self.retailer == "Nykaa":
            return f"https://www.nykaa.com/search/result/?q={query}"
        if self.retailer == "Lenskart":
            return f"https://www.lenskart.com/search?q={query}"
        return f"https://www.amazon.in/s?k={query}"


PRODUCTS = (
    Product(
        "maybelline-nude-nuance",
        "Color Sensational Creamy Matte Lipstick — Nude Nuance",
        "Maybelline New York",
        "Nykaa",
        "Maybelline Color Sensational Creamy Matte Lipstick Nude Nuance",
        299,
        "makeup",
        frozenset({"lip", "neutral", "olive", "medium", "tan"}),
        "#A5756B",
        "Nude Nuance",
    ),
    Product(
        "lakme-blush-nude",
        "9to5 Primer + Matte Lip Color — Blush Nude",
        "Lakmé",
        "Nykaa",
        "Lakme 9to5 Primer Matte Lip Color Blush Nude",
        550,
        "makeup",
        frozenset({"lip", "cool", "neutral", "light", "medium"}),
        "#B16E73",
        "Blush Nude",
    ),
    Product(
        "lakme-terracotta-lip",
        "9to5 Primer + Matte Lip Color — Terracotta",
        "Lakmé",
        "Nykaa",
        "Lakme 9to5 Primer Matte Lip Color Terracotta",
        550,
        "makeup",
        frozenset({"lip", "warm", "olive", "tan", "deep"}),
        "#B75B3F",
        "Terracotta",
    ),
    Product(
        "kay-beauty-rustic-rush",
        "Matte Blush — Rustic Rush",
        "Kay Beauty",
        "Nykaa",
        "Kay Beauty Matte Blush Rustic Rush",
        799,
        "makeup",
        frozenset({"cheek", "warm", "olive", "medium", "deep"}),
        "#B86756",
        "Rustic Rush",
    ),
    Product(
        "kay-beauty-rosy-rush",
        "Matte Blush — Rosy Rush",
        "Kay Beauty",
        "Nykaa",
        "Kay Beauty Matte Blush Rosy Rush",
        799,
        "makeup",
        frozenset({"cheek", "cool", "neutral", "fair", "light", "medium"}),
        "#C27C88",
        "Rosy Rush",
    ),
    Product(
        "swiss-beauty-copper-palette",
        "Ultimate 9 Pigmented Colours Eyeshadow Palette — Copper",
        "Swiss Beauty",
        "Nykaa",
        "Swiss Beauty Ultimate 9 Pigmented Colors Eyeshadow Palette Copper",
        399,
        "makeup",
        frozenset({"eye", "warm", "neutral", "medium", "tan"}),
        "#9B704A",
        "Copper tones",
    ),
    Product(
        "philips-bhb862-curler",
        "BHB862/00 Essential Care Hair Curler",
        "Philips",
        "Amazon India",
        "Philips BHB862/00 Essential Care Hair Curler",
        2299,
        "hair",
        frozenset({"hair.long_waves", "hair.soft_waves", "hair.shoulder_waves", "hair.long_layers"}),
    ),
    Product(
        "vega-vhsh18-straightener",
        "VHSH-18 Vital Hair Straightener",
        "VEGA",
        "Amazon India",
        "VEGA VHSH-18 Vital Hair Straightener",
        999,
        "hair",
        frozenset({"hair.sleek_crop", "hair.long_sleek", "hair.slick_back"}),
    ),
    Product(
        "vincent-chase-rectangle",
        "Full Rim Rectangle Eyeglasses",
        "Vincent Chase",
        "Lenskart",
        "Vincent Chase full rim rectangle eyeglasses",
        999,
        "eyewear",
        frozenset({"eyewear.angular_rectangle", "eyewear.rectangle", "eyewear.wayfarer"}),
    ),
    Product(
        "lenskart-cat-eye",
        "Full Rim Cat-Eye Eyeglasses",
        "Lenskart",
        "Lenskart",
        "full rim cat eye eyeglasses",
        1499,
        "eyewear",
        frozenset({"eyewear.cat_eye", "eyewear.soft_cat_eye", "eyewear.light_cat_eye", "eyewear.upswept"}),
    ),
    Product(
        "uniqlo-crew-tee",
        "AIRism Cotton Crew Neck T-Shirt",
        "UNIQLO",
        "Amazon India",
        "UNIQLO AIRism Cotton Crew Neck T-Shirt women",
        1490,
        "outfit_cut",
        frozenset({"cut.crew", "cut.high_crew"}),
        "#F2EEE8",
        "Soft white",
    ),
    Product(
        "hm-v-neck-top",
        "Ladies Cotton V-Neck Top",
        "H&M",
        "Amazon India",
        "H&M ladies cotton V-neck top",
        1299,
        "outfit_cut",
        frozenset({"cut.v_neck", "cut.deep_v", "cut.narrow_v"}),
        "#C27C88",
        "Dusty rose",
    ),
    Product(
        "westside-olive-tee",
        "Nuon Solid Crew-Neck T-Shirt",
        "Westside",
        "Amazon India",
        "Westside Nuon solid crew neck t shirt olive green",
        799,
        "outfit_color",
        frozenset({"color"}),
        "#778044",
        "Olive",
    ),
    Product(
        "hm-coral-top",
        "Ladies Cotton Top",
        "H&M",
        "Amazon India",
        "H&M ladies cotton top coral",
        1299,
        "outfit_color",
        frozenset({"color"}),
        "#E87562",
        "Coral",
    ),
)


def _color_distance(left: str, right: str) -> float:
    left_rgb = tuple(int(left[index : index + 2], 16) for index in (1, 3, 5))
    right_rgb = tuple(int(right[index : index + 2], 16) for index in (1, 3, 5))
    return sum((a - b) ** 2 for a, b in zip(left_rgb, right_rgb, strict=True)) ** 0.5


def match_products(report_data: dict, budget: schemas.ProductBudgetFilter | None) -> schemas.ProductMatchesResponse:
    """Return only explicit attribute matches; never substitute unrelated products."""
    features = report_data["features"]
    groups: list[schemas.ProductRecommendationMatch] = []
    for group in report_data["recommendations"]:
        for recommendation in group["items"]:
            product_matches: list[tuple[Product, float, str]] = []
            recommendation_id = recommendation["id"]
            recommendation_category = group["category"]
            for product in PRODUCTS:
                distance: float | None = None
                if recommendation_category == "makeup" and product.category == "makeup":
                    makeup_kind = recommendation_id.split(".")[1]
                    if makeup_kind != next((tag for tag in product.tags if tag in {"lip", "cheek", "eye"}), None):
                        continue
                    distance = _color_distance(recommendation["color_hex"], product.color_hex)
                    if distance > 145:
                        continue
                elif recommendation_category == "outfit_color" and product.category == "outfit_color":
                    distance = _color_distance(recommendation["color_hex"], product.color_hex)
                    if distance > 110:
                        continue
                else:
                    tag_prefix = {"hair": "hair", "eyewear": "eyewear", "outfit_cut": "cut"}.get(recommendation_category)
                    if tag_prefix is None:
                        continue
                    attribute = recommendation_id.split(".", 1)[1] if tag_prefix != "cut" else recommendation_id.rsplit(".", 1)[1]
                    if product.category != recommendation_category and not (
                        recommendation_category == "outfit_cut" and product.category == "outfit_cut"
                    ):
                        continue
                    if f"{tag_prefix}.{attribute}" not in product.tags:
                        continue

                if budget == "low" and product.price_inr > 500:
                    continue
                if budget == "mid" and product.price_inr > 1500:
                    continue

                score = 1 - distance / 255 if distance is not None else 0.9
                if product.category == "makeup":
                    tone = features["undertone"]["value"]
                    if tone in product.tags or tone == "neutral":
                        score += 0.05
                    else:
                        score -= 0.05
                reason = (
                    f"Matches the {recommendation['label']} recommendation by product type and shade colour."
                    if distance is not None and product.category == "makeup"
                    else f"Matches the {recommendation['label']} recommendation by style attribute."
                )
                product_matches.append((product, max(0, min(1, score)), reason))

            product_matches.sort(key=lambda match: (-match[1], match[0].price_inr, match[0].id))
            groups.append(
                schemas.ProductRecommendationMatch(
                    recommendation_id=recommendation_id,
                    recommendation_label=recommendation["label"],
                    category=recommendation_category,
                    products=[
                        schemas.ProductMatch(
                            id=product.id,
                            name=product.name,
                            brand=product.brand,
                            retailer=product.retailer,
                            listing_url=product.listing_url,
                            price_inr=product.price_inr,
                            budget=product.budget,
                            shade_name=product.shade_name,
                            color_hex=product.color_hex,
                            match_score=round(score, 2),
                            match_reason=reason,
                        )
                        for product, score, reason in product_matches[:2]
                    ],
                )
            )
    return schemas.ProductMatchesResponse(
        currency="INR",
        budget_filter=budget or "all",
        price_disclaimer=(
            "Curated reference prices in INR; retailer price, stock, colour, and availability may change. Confirm before purchase."
        ),
        matches=groups,
    )
