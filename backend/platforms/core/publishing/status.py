from enum import StrEnum


class TargetStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PUBLISHING = "publishing"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def running(cls) -> tuple["TargetStatus", ...]:
        return (cls.VALIDATING, cls.UPLOADING, cls.PROCESSING, cls.PUBLISHING)

    @classmethod
    def active(cls) -> tuple["TargetStatus", ...]:
        return (cls.QUEUED, *cls.running())

    @property
    def is_active(self) -> bool:
        return self in self.active()
