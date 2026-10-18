from typing import ClassVar

from django.conf import settings
from pydantic import BaseModel, Field, field_validator

from platforms import PlatformCatalog
from platforms.core import PlatformType


class LoginSchema(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PreferencesSchema(BaseModel):
    FIELDS: ClassVar = {
        "mediaRetentionDays": "media_retention_days",
        "defaultPlatforms": "default_platforms",
        "platformDefaults": "platform_defaults",
    }

    mediaRetentionDays: int | None = None
    defaultPlatforms: list[PlatformType] = Field(default_factory=list)
    platformDefaults: dict[PlatformType, dict] = Field(default_factory=dict)

    @field_validator("mediaRetentionDays")
    @classmethod
    def offered_retention(cls, days: int | None) -> int | None:
        if days is not None and days not in settings.MEDIA_RETENTION_DAYS_CHOICES:
            raise ValueError(f"must be one of {settings.MEDIA_RETENTION_DAYS_CHOICES} or null")
        return days

    @field_validator("defaultPlatforms")
    @classmethod
    def each_platform_once(cls, platforms: list[PlatformType]) -> list[PlatformType]:
        if len(platforms) != len(set(platforms)):
            raise ValueError("each platform can be selected once")
        return platforms

    @field_validator("platformDefaults")
    @classmethod
    def settings_the_platforms_accept(cls, defaults: dict[PlatformType, dict]) -> dict[PlatformType, dict]:
        for platform, raw in defaults.items():
            if not PlatformCatalog.is_exact_settings(platform, raw):
                raise ValueError(f"invalid settings for {platform}")
        return defaults

    def as_fields(self) -> dict:
        given = self.model_dump(mode="json", include=self.model_fields_set)
        return {self.FIELDS[name]: value for name, value in given.items()}
