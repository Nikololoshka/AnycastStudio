from pydantic import AwareDatetime, BaseModel, Field, field_validator

from platforms import PlatformCatalog
from platforms.core import PlatformType
from services.core.publications import NewPublication, NewTarget


class TargetSchema(BaseModel):
    platform: PlatformType
    socialAccountId: int
    settings: dict = Field(default_factory=dict)


class CreatePublicationSchema(BaseModel):
    mediaAssetId: int
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10_000)
    hashtags: list[str] = Field(default_factory=list, max_length=60)
    publishAt: AwareDatetime | None = None
    targets: list[TargetSchema] = Field(min_length=1, max_length=4)

    @field_validator("targets")
    @classmethod
    def one_target_per_platform(cls, targets: list[TargetSchema]) -> list[TargetSchema]:
        platforms = [target.platform for target in targets]
        if len(platforms) != len(set(platforms)):
            raise ValueError("only one target per platform")
        return targets

    def as_new_publication(self, owner_id: int) -> NewPublication:
        return NewPublication(
            owner_id=owner_id,
            asset_id=self.mediaAssetId,
            title=self.title,
            description=self.description,
            hashtags=tuple(self.hashtags),
            publish_at=self.publishAt,
            targets=tuple(
                NewTarget(target.platform, target.socialAccountId, target.settings) for target in self.targets
            ),
        )


class DraftSchema(BaseModel):
    mediaAssetId: int | None = None
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=10_000)
    hashtags: list[str] = Field(default_factory=list, max_length=60)
    publishAt: AwareDatetime | None = None
    selectedPlatforms: list[PlatformType] = Field(default_factory=list)
    platformSettings: dict[PlatformType, dict] = Field(default_factory=dict)

    @field_validator("selectedPlatforms")
    @classmethod
    def each_platform_once(cls, platforms: list[PlatformType]) -> list[PlatformType]:
        if len(platforms) != len(set(platforms)):
            raise ValueError("each platform can be selected once")
        return platforms

    @field_validator("platformSettings")
    @classmethod
    def settings_the_platforms_accept(cls, settings: dict[PlatformType, dict]) -> dict[PlatformType, dict]:
        for platform, raw in settings.items():
            if not PlatformCatalog.is_exact_settings(platform, raw):
                raise ValueError(f"invalid settings for {platform}")
        return settings

    def as_fields(self) -> dict:
        return {
            "asset_id": self.mediaAssetId,
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
            "publish_at": self.publishAt,
            "selected_platforms": [str(platform) for platform in self.selectedPlatforms],
            "platform_settings": {str(platform): raw for platform, raw in self.platformSettings.items()},
        }
