from pydantic import BaseModel, ConfigDict


class TikTokAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
