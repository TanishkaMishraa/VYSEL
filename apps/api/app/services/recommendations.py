"""Deterministic, explainable styling rules for explicitly estimated face attributes."""

from dataclasses import dataclass
from typing import Literal

from app import schemas
from app.models import UserPreferences

Budget = Literal["low", "mid", "high"]
Style = Literal["everyday", "minimal", "classic", "bold", "formal"]
Category = schemas.RecommendationCategory

BUDGET_ORDER: dict[str, int] = {"low": 0, "mid": 1, "high": 2}
SCORING_WEIGHTS = schemas.RecommendationScoring(feature_fit=0.5, style_goal=0.2, personal_style=0.1, occasion=0.1, budget=0.1)

SEASON_PALETTES: dict[schemas.Season, list[schemas.PaletteColor]] = {
    "spring": [
        schemas.PaletteColor(name="Coral", hex="#E87562", role="accent", wear="Lips, scarves, and near-face accents"),
        schemas.PaletteColor(name="Warm ivory", hex="#F4E8D0", role="neutral", wear="Shirts and soft neutrals"),
        schemas.PaletteColor(name="Leaf green", hex="#78A85B", role="base", wear="Everyday tops and knitwear"),
        schemas.PaletteColor(name="Turquoise", hex="#38A8A0", role="accent", wear="Accessories and statement pieces"),
        schemas.PaletteColor(name="Camel", hex="#B9844D", role="neutral", wear="Outerwear and everyday layers"),
    ],
    "summer": [
        schemas.PaletteColor(name="Dusty rose", hex="#C27C88", role="accent", wear="Lips, scarves, and near-face accents"),
        schemas.PaletteColor(name="Soft white", hex="#F2EEE8", role="neutral", wear="Shirts and soft neutrals"),
        schemas.PaletteColor(name="Sage", hex="#91A88A", role="base", wear="Everyday tops and knitwear"),
        schemas.PaletteColor(name="Periwinkle", hex="#8995C4", role="accent", wear="Accessories and statement pieces"),
        schemas.PaletteColor(name="Slate blue", hex="#60758C", role="neutral", wear="Tailoring and everyday layers"),
    ],
    "autumn": [
        schemas.PaletteColor(name="Terracotta", hex="#C56845", role="accent", wear="Lips, scarves, and near-face accents"),
        schemas.PaletteColor(name="Warm cream", hex="#E8D9B8", role="neutral", wear="Shirts and soft neutrals"),
        schemas.PaletteColor(name="Olive", hex="#778044", role="base", wear="Everyday tops and knitwear"),
        schemas.PaletteColor(name="Rust", hex="#A64F32", role="accent", wear="Accessories and statement pieces"),
        schemas.PaletteColor(name="Deep teal", hex="#356B67", role="neutral", wear="Tailoring and everyday layers"),
    ],
    "winter": [
        schemas.PaletteColor(name="Berry", hex="#A52F58", role="accent", wear="Lips, scarves, and near-face accents"),
        schemas.PaletteColor(name="Optic white", hex="#F7F7F5", role="neutral", wear="Shirts and crisp neutrals"),
        schemas.PaletteColor(name="Emerald", hex="#13795B", role="base", wear="Everyday tops and knitwear"),
        schemas.PaletteColor(name="Cobalt", hex="#2853A6", role="accent", wear="Accessories and statement pieces"),
        schemas.PaletteColor(name="Ink navy", hex="#202B47", role="neutral", wear="Tailoring and everyday layers"),
    ],
}


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    category: Category
    budget: Budget
    styles: tuple[str, ...]
    goals: tuple[str, ...]
    occasions: tuple[str, ...]
    reason: str
    fit: float
    color_hex: str | None = None
    feature_confidence: float = 1.0


HAIR: dict[str, tuple[tuple[str, str, float], ...]] = {
    "oval": (
        ("soft_layers", "Soft face-framing layers", 0.9),
        ("textured_bob", "Textured bob", 0.86),
        ("side_swept_fringe", "Side-swept fringe", 0.82),
        ("long_waves", "Long, loose waves", 0.8),
        ("sleek_crop", "Sleek cropped cut", 0.76),
    ),
    "round": (
        ("long_layers", "Long, face-framing layers", 0.92),
        ("side_part", "Deep side part with length", 0.88),
        ("collarbone_cut", "Collarbone-length cut", 0.84),
        ("textured_pixie", "Textured pixie with crown lift", 0.78),
        ("chin_bob", "Soft, below-chin bob", 0.72),
    ),
    "square": (
        ("soft_waves", "Soft, long waves", 0.92),
        ("curtain_fringe", "Curtain fringe with layers", 0.88),
        ("wispy_lob", "Wispy, collarbone-length lob", 0.84),
        ("side_swept_layers", "Side-swept face-framing layers", 0.8),
        ("blunt_jaw_bob", "Blunt jaw-length bob", 0.7),
    ),
    "heart": (
        ("chin_lob", "Chin-length textured lob", 0.92),
        ("side_fringe", "Soft side fringe", 0.88),
        ("jaw_layers", "Jaw-skimming layers", 0.84),
        ("long_layers", "Long, softly layered cut", 0.78),
        ("crown_volume", "Low-volume crown with textured ends", 0.74),
    ),
    "oblong": (
        ("curtain_bangs", "Curtain bangs with soft layers", 0.92),
        ("shoulder_waves", "Shoulder-length waves", 0.88),
        ("full_fringe", "Soft full fringe", 0.84),
        ("chin_bob", "Chin-length textured bob", 0.8),
        ("long_sleek", "Long, sleek length", 0.68),
    ),
    "diamond": (
        ("chin_layers", "Chin-length layers", 0.92),
        ("side_fringe", "Side-swept fringe", 0.88),
        ("textured_lob", "Textured collarbone lob", 0.84),
        ("soft_bob", "Soft, cheekbone-skimming bob", 0.8),
        ("slick_back", "Sleek, pulled-back style", 0.74),
    ),
}

FRAMES: dict[str, tuple[tuple[str, str, float], ...]] = {
    "oval": (
        ("soft_square", "Soft-square frames", 0.9),
        ("browline", "Browline frames", 0.86),
        ("round", "Round frames", 0.82),
        ("cat_eye", "Subtle cat-eye frames", 0.8),
        ("rectangle", "Slim rectangular frames", 0.78),
    ),
    "round": (
        ("angular_rectangle", "Angular rectangular frames", 0.92),
        ("geometric", "Geometric frames", 0.88),
        ("browline", "Defined browline frames", 0.84),
        ("upswept", "Lightly upswept frames", 0.8),
        ("round", "Round frames", 0.68),
    ),
    "square": (
        ("round", "Rounded frames", 0.92),
        ("oval", "Oval frames", 0.88),
        ("thin_metal", "Fine metal frames", 0.84),
        ("soft_cat_eye", "Soft cat-eye frames", 0.8),
        ("angular_square", "Angular square frames", 0.68),
    ),
    "heart": (
        ("light_oval", "Lightweight oval frames", 0.92),
        ("rimless", "Rimless frames", 0.88),
        ("bottom_heavy", "Frames with a subtle lower rim", 0.84),
        ("light_cat_eye", "Light, narrow cat-eye frames", 0.8),
        ("heavy_browline", "Heavy browline frames", 0.68),
    ),
    "oblong": (
        ("tall_square", "Tall square frames", 0.92),
        ("deep_oval", "Deep oval frames", 0.88),
        ("decorative_temple", "Frames with decorative temples", 0.84),
        ("wayfarer", "Classic wayfarer frames", 0.8),
        ("narrow_rectangle", "Narrow rectangular frames", 0.68),
    ),
    "diamond": (
        ("browline", "Browline frames", 0.92),
        ("cat_eye", "Cat-eye frames", 0.88),
        ("oval", "Oval frames", 0.84),
        ("rimless", "Rimless frames", 0.8),
        ("narrow_rectangle", "Narrow rectangular frames", 0.7),
    ),
}


def _season(features: schemas.RecommendationFeatures) -> schemas.SeasonEstimate:
    undertone = features.undertone.value
    contrast = features.contrast.value
    depth = features.skin_depth.value

    if undertone == "warm":
        value: schemas.Season = "autumn" if contrast == "high" or depth == "deep" else "spring"
    elif undertone == "cool":
        value = "winter" if contrast == "high" or depth == "deep" else "summer"
    else:
        value = "winter" if contrast == "high" else "summer" if contrast == "low" else "autumn" if depth == "deep" else "spring"

    evidence = (features.undertone.confidence + features.contrast.confidence + features.skin_depth.confidence) / 3
    confidence = round(min(0.7, evidence * 0.75), 2)
    return schemas.SeasonEstimate(
        value=value,
        confidence=confidence,
        rationale=(
            f"A preliminary {value.title()} palette is suggested from the estimated undertone, feature contrast, and skin depth. "
            "Seasonal colour analysis is subjective."
        ),
    )


def _candidates(features: schemas.RecommendationFeatures, season: schemas.SeasonEstimate) -> list[Candidate]:
    shape = features.face_shape.value
    undertone = features.undertone.value
    depth = features.skin_depth.value
    result: list[Candidate] = []

    for index, (key, label, fit) in enumerate(HAIR[shape]):
        result.append(
            Candidate(
                f"hair.{key}",
                label,
                "hair",
                ("low", "mid", "mid", "low", "high")[index],
                ("everyday", "classic") if index in (0, 1, 2) else ("minimal", "bold"),
                ("hair", "everyday_refresh"),
                ("everyday", "work", "travel"),
                f"Often used to balance a {shape} face shape; personal preference and hair texture matter.",
                fit,
                feature_confidence=features.face_shape.confidence,
            )
        )

    for index, (key, label, fit) in enumerate(FRAMES[shape]):
        result.append(
            Candidate(
                f"eyewear.{key}",
                label,
                "eyewear",
                ("low", "mid", "low", "mid", "high")[index],
                ("everyday", "classic") if index < 3 else ("minimal", "bold"),
                ("eyewear", "everyday_refresh"),
                ("everyday", "work", "interviews"),
                f"The frame outline is a styling starting point for a {shape} face shape, not a fit guarantee.",
                fit,
                feature_confidence=features.face_shape.confidence,
            )
        )

    makeup = (
        ("lip", "Soft rose lip", "#B85F70", "cool", "light", 0.87),
        ("cheek", "Muted berry blush", "#A64F69", "cool", "deep", 0.84),
        ("lip", "Warm coral lip", "#D76F53", "warm", "light", 0.88),
        ("cheek", "Terracotta blush", "#B75B3F", "warm", "deep", 0.85),
        ("lip", "Balanced rose-mauve lip", "#A76572", "neutral", "medium", 0.86),
        ("eye", "Soft bronze eye colour", "#9B704A", "warm", "medium", 0.8),
        ("lip", "Muted rosewood lip", "#98604F", "olive", "tan", 0.85),
        ("cheek", "Soft apricot blush", "#C77B59", "olive", "medium", 0.82),
    )
    for index, (kind, label, color, tone, recommended_depth, base_fit) in enumerate(makeup):
        fit = base_fit
        if tone == undertone:
            fit += 0.08
        elif undertone == "neutral":
            fit += 0.03
        else:
            fit -= 0.04
        if recommended_depth == depth:
            fit += 0.03
        result.append(
            Candidate(
                f"makeup.{kind}.{index}",
                label,
                "makeup",
                "low" if index % 2 == 0 else "mid",
                ("everyday", "minimal") if index in (0, 4) else ("everyday", "bold"),
                ("makeup", "palette"),
                ("everyday", "work", "dates", "evening"),
                (
                    f"A {tone}-leaning shade is a starting point for an estimated {undertone} undertone and {depth} skin depth; "
                    "try it in natural light."
                ),
                max(0, min(1, fit)),
                color,
                feature_confidence=(features.undertone.confidence + features.skin_depth.confidence) / 2,
            )
        )

    palette = SEASON_PALETTES[season.value]
    for index, color in enumerate(palette):
        result.append(
            Candidate(
                f"outfit_color.{season.value}.{index}",
                color.name,
                "outfit_color",
                ("low", "mid", "low", "mid", "high")[index],
                ("everyday", "classic", "minimal") if color.role != "accent" else ("bold", "everyday"),
                ("palette", "everyday_refresh"),
                ("everyday", "work", "festive", "evening", "dates", "travel"),
                f"Part of the provisional {season.value.title()} palette; wear it {color.wear.lower()}.",
                0.74 + (0.06 if color.role == "base" else 0.02 if color.role == "neutral" else 0),
                color.hex,
                feature_confidence=season.confidence,
            )
        )

    neckline_rules: dict[str, tuple[tuple[str, str, float], ...]] = {
        "oval": (("crew", "Crew neck", 0.87), ("v_neck", "V-neck", 0.86), ("scoop", "Scoop neck", 0.84), ("square", "Square neck", 0.82)),
        "round": (
            ("v_neck", "V-neck", 0.92),
            ("scoop", "Open scoop neck", 0.88),
            ("sweetheart", "Sweetheart neckline", 0.84),
            ("crew", "High crew neck", 0.72),
        ),
        "square": (
            ("scoop", "Scoop neck", 0.92),
            ("round", "Rounded neckline", 0.88),
            ("sweetheart", "Soft sweetheart neckline", 0.86),
            ("square", "Square neck", 0.74),
        ),
        "heart": (
            ("boat", "Boat neck", 0.9),
            ("crew", "Crew neck", 0.88),
            ("square", "Square neck", 0.84),
            ("v_neck", "Deep V-neck", 0.76),
        ),
        "oblong": (
            ("boat", "Boat neck", 0.92),
            ("crew", "Crew neck", 0.88),
            ("wide_scoop", "Wide scoop neck", 0.86),
            ("deep_v", "Deep V-neck", 0.72),
        ),
        "diamond": (
            ("boat", "Boat neck", 0.9),
            ("scoop", "Scoop neck", 0.88),
            ("sweetheart", "Sweetheart neckline", 0.86),
            ("narrow_v", "Narrow V-neck", 0.78),
        ),
    }
    for index, (key, label, fit) in enumerate(neckline_rules[shape]):
        result.append(
            Candidate(
                f"outfit_cut.{key}",
                label,
                "outfit_cut",
                ("low", "low", "mid", "mid")[index],
                ("everyday", "classic") if index < 2 else ("minimal", "formal"),
                ("everyday_refresh", "special_occasion"),
                ("everyday", "work", "interviews", "festive", "evening", "dates"),
                f"A neckline to explore with a {shape} face shape; this is a personal styling suggestion, not a body-fit assessment.",
                fit,
                feature_confidence=features.face_shape.confidence,
            )
        )
    return result


def _preference_score(candidate: Candidate, preferences: UserPreferences | None) -> float:
    if preferences is None:
        return 0.26

    goals = set(preferences.style_goals or [])
    categories = set(preferences.categories or [])
    occasions = set(preferences.occasions or [])
    goal_score = 1.0 if goals.intersection(candidate.goals) or candidate.category in categories else 0.35 if goals or categories else 0.65
    style_score = 0.65 if not preferences.style else 1.0 if preferences.style in candidate.styles else 0.45
    occasion_score = 0.65 if not occasions else 1.0 if occasions.intersection(candidate.occasions) else 0.45
    return (
        SCORING_WEIGHTS.style_goal * goal_score + SCORING_WEIGHTS.personal_style * style_score + SCORING_WEIGHTS.occasion * occasion_score
    )


def generate_recommendations(
    features: schemas.RecommendationFeatures, preferences: UserPreferences | None, limit_per_category: int = 3
) -> schemas.RecommendationsResponse:
    """Rank styling options using explainable feature, goal, style, occasion and budget rules."""
    season = _season(features)
    palette = SEASON_PALETTES[season.value]
    ranked: dict[str, list[schemas.RecommendationItem]] = {}

    for candidate in _candidates(features, season):
        preference_score = _preference_score(candidate, preferences)
        feature_fit = 0.5 + (candidate.fit - 0.5) * candidate.feature_confidence
        if preferences is None or preferences.budget is None:
            budget_score, within_budget = 0.65, None
        else:
            within_budget = BUDGET_ORDER[candidate.budget] <= BUDGET_ORDER[preferences.budget]
            budget_score = 1.0 if within_budget else 0.2
        score = SCORING_WEIGHTS.feature_fit * feature_fit + preference_score + SCORING_WEIGHTS.budget * budget_score
        item = schemas.RecommendationItem(
            id=candidate.id,
            label=candidate.label,
            reason=candidate.reason,
            score=round(min(1, score), 3),
            budget=candidate.budget,
            within_budget=within_budget,
            color_hex=candidate.color_hex,
        )
        ranked.setdefault(candidate.category, []).append(item)

    groups = [
        schemas.RecommendationGroup(category=category, items=sorted(items, key=lambda item: (-item.score, item.id))[:limit_per_category])
        for category, items in ranked.items()
    ]
    return schemas.RecommendationsResponse(
        features=features,
        season=season,
        palette=palette,
        recommendations=groups,
        scoring=SCORING_WEIGHTS,
        disclaimer=(
            "Suggestions are rule-based style ideas from user-provided estimates and preferences, not a diagnosis or result "
            "of image analysis. Face shape, undertone, skin depth, and seasonal colour are subjective; treat every suggestion "
            "as optional and try colours in natural light."
        ),
    )
