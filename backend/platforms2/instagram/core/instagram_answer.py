from pydantic import BaseModel, ConfigDict


class InstagramAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
