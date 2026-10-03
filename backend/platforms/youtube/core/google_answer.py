from pydantic import BaseModel, ConfigDict


class GoogleAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
