from pydantic import BaseModel, Field


class StartUploadSchema(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    sizeBytes: int = Field(gt=0)
    mimeType: str = Field(max_length=100)
    sha256: str = Field(default="", max_length=64)


class CompleteUploadSchema(BaseModel):
    durationSeconds: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
