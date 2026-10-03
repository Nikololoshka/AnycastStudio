from enum import StrEnum
from typing import Self


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
    def running(cls) -> tuple[Self, ...]:
        return (cls.VALIDATING, cls.UPLOADING, cls.PROCESSING, cls.PUBLISHING)

    @classmethod
    def worked_on(cls) -> tuple[Self, ...]:
        return (cls.VALIDATING, cls.UPLOADING, cls.PUBLISHING)

    @classmethod
    def active(cls) -> tuple[Self, ...]:
        return (cls.QUEUED, *cls.running())

    @property
    def is_active(self) -> bool:
        return self in self.active()
