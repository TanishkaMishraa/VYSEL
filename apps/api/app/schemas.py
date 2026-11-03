"""Request/response models — the wire format from docs/api/openapi.yaml."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ── Shared vocabularies (keep in sync with apps/web/lib/preferences.ts) ──
Budget = Literal["low", "mid", "high"]
StylePreference = Literal["everyday", "minimal", "classic", "bold", "formal"]
Category = Literal["hair", "eyewear", "makeup"]
StyleGoal = Literal["hair", "eyewear", "makeup", "palette", "everyday_refresh", "special_occasion"]
Occasion = Literal["everyday", "work", "interviews", "festive", "evening", "dates", "travel"]

Password = Field(min_length=10, max_length=128)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Auth ──


class RegisterRequest(Strict):
    email: EmailStr = Field(max_length=254)
    password: str = Password
    display_name: str = Field(min_length=1, max_length=50)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Display name can't be blank")
        return v.strip()


class LoginRequest(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(Strict):
    email: EmailStr


class ResetPasswordRequest(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Password


class Providers(BaseModel):
    password: bool = True
    google: bool


# ── Profile ──


class Preferences(BaseModel):
    style_goals: list[StyleGoal] = []
    occasions: list[Occasion] = []
    budget: Budget | None = None
    style: StylePreference | None = None
    categories: list[Category] = []

    model_config = ConfigDict(from_attributes=True)


class PreferencesUpdate(Strict):
    """Merge-patch: omitted fields keep their value; null clears a scalar."""

    style_goals: list[StyleGoal] | None = Field(default=None, max_length=6)
    occasions: list[Occasion] | None = Field(default=None, max_length=7)
    budget: Budget | None = None
    style: StylePreference | None = None
    categories: list[Category] | None = Field(default=None, max_length=3)

    @field_validator("style_goals", "occasions", "categories")
    @classmethod
    def _unique(cls, v: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(v)) if v is not None else v


class Profile(BaseModel):
    id: str
    email: str
    display_name: str
    email_verified: bool
    has_password: bool
    auth_providers: list[str]
    preferences: Preferences
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(Strict):
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    preferences: PreferencesUpdate | None = None
    # Set true when the onboarding questionnaire is submitted.
    onboarding_completed: bool | None = None


# ── Explainable recommendations ──

FaceShape = Literal["oval", "round", "square", "heart", "oblong", "diamond"]
Undertone = Literal["warm", "cool", "neutral", "olive"]
SkinDepth = Literal["fair", "light", "medium", "tan", "deep"]
FeatureContrast = Literal["low", "medium", "high"]
RecommendationCategory = Literal["hair", "eyewear", "makeup", "outfit_color", "outfit_cut"]
Season = Literal["spring", "summer", "autumn", "winter"]


class FaceShapeEstimate(Strict):
    value: FaceShape
    confidence: float = Field(ge=0, le=1)


class UndertoneEstimate(Strict):
    value: Undertone
    confidence: float = Field(ge=0, le=1)


class SkinDepthEstimate(Strict):
    value: SkinDepth
    confidence: float = Field(ge=0, le=1)


class ContrastEstimate(Strict):
    value: FeatureContrast
    confidence: float = Field(ge=0, le=1)


class RecommendationFeatures(Strict):
    face_shape: FaceShapeEstimate
    undertone: UndertoneEstimate
    skin_depth: SkinDepthEstimate
    contrast: ContrastEstimate = Field(default_factory=lambda: ContrastEstimate(value="medium", confidence=0.5))


class PaletteColor(BaseModel):
    name: str
    hex: str
    role: Literal["base", "accent", "neutral"]
    wear: str


class SeasonEstimate(BaseModel):
    value: Season
    confidence: float = Field(ge=0, le=0.7)
    rationale: str


class RecommendationItem(BaseModel):
    id: str
    label: str
    reason: str
    score: float = Field(ge=0, le=1)
    budget: Budget
    within_budget: bool | None
    color_hex: str | None = None


class RecommendationGroup(BaseModel):
    category: RecommendationCategory
    items: list[RecommendationItem]


class RecommendationScoring(BaseModel):
    feature_fit: float
    style_goal: float
    personal_style: float
    occasion: float
    budget: float


class RecommendationsResponse(BaseModel):
    features: RecommendationFeatures
    season: SeasonEstimate
    palette: list[PaletteColor]
    recommendations: list[RecommendationGroup]
    scoring: RecommendationScoring
    disclaimer: str


class CreateReportRequest(Strict):
    features: RecommendationFeatures


class ReportFeedbackOut(BaseModel):
    recommendation_id: str
    helpful: bool
    updated_at: datetime


class ReportOut(BaseModel):
    id: str
    created_at: datetime
    report_data: RecommendationsResponse
    share_enabled: bool
    feedback: list[ReportFeedbackOut] = Field(default_factory=list)


class ReportListItem(BaseModel):
    id: str
    created_at: datetime
    season: Season
    recommendation_count: int
    share_enabled: bool


class ShareLinkOut(BaseModel):
    share_url: str


class ReportFeedbackRequest(Strict):
    recommendation_id: str = Field(min_length=1, max_length=100)
    helpful: bool


SavedLookOccasion = Literal["college", "office", "party", "wedding"]


class SavedLookLayer(Strict):
    enabled: bool
    shade_id: str = Field(min_length=1, max_length=100)
    shade_name: str = Field(min_length=1, max_length=60)
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    intensity: float = Field(ge=0, le=1)


class SavedLinerLayer(SavedLookLayer):
    wing: bool


class SavedLookData(Strict):
    lips: SavedLookLayer
    blush: SavedLookLayer
    liner: SavedLinerLayer


class CreateSavedLookRequest(Strict):
    name: str = Field(min_length=1, max_length=60)
    occasion: SavedLookOccasion
    look: SavedLookData

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Look name can't be blank")
        return value.strip()


class SavedLookOut(BaseModel):
    id: str
    name: str
    occasion: SavedLookOccasion
    look: SavedLookData
    created_at: datetime
    updated_at: datetime


class AuthSession(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 — the auth scheme, not a secret
    expires_in: int
    user: Profile
