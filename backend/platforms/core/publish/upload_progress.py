from dataclasses import dataclass


@dataclass(frozen=True)
class UploadProgress:
    uploaded_bytes: int
    total_bytes: int
    media_id: str | None = None

    @property
    def percent(self) -> int:
        return 100 if self.total_bytes == 0 else self.uploaded_bytes * 100 // self.total_bytes

    @property
    def done(self) -> bool:
        return self.media_id is not None
