from pydantic import AwareDatetime, BaseModel, Field, field_validator

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
