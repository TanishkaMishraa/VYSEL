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


class AuthSession(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 — the auth scheme, not a secret
    expires_in: int
    user: Profile
