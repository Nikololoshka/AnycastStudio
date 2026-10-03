from pydantic import AwareDatetime, BaseModel, Field, field_validator

from platforms2.core import PlatformType


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
