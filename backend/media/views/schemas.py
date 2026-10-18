from typing import ClassVar

from pydantic import Base64Bytes, BaseModel, Field, field_validator


class StartUploadSchema(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    sizeBytes: int = Field(gt=0)
    mimeType: str = Field(max_length=100)
    sha256: str = Field(default="", max_length=64)


class CompleteUploadSchema(BaseModel):
    durationSeconds: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    thumbnailJpeg: Base64Bytes | None = None

    MAX_THUMBNAIL_BYTES: ClassVar = 200 * 1024
    JPEG_SIGNATURE: ClassVar = b"\xff\xd8\xff"

    @field_validator("thumbnailJpeg")
    @classmethod
    def small_jpeg(cls, thumbnail: bytes | None) -> bytes | None:
        if thumbnail is None:
            return None
        if len(thumbnail) > cls.MAX_THUMBNAIL_BYTES:
            raise ValueError(f"thumbnail is larger than {cls.MAX_THUMBNAIL_BYTES} bytes")
        if not thumbnail.startswith(cls.JPEG_SIGNATURE):
            raise ValueError("thumbnail is not a JPEG")
        return thumbnail
