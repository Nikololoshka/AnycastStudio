from pydantic import BaseModel, ConfigDict


class XAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
