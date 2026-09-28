from abc import ABC, abstractmethod

from ..publishing import PublishJob


class TargetRepository(ABC):
    @abstractmethod
    def job_of(self, target_id: int) -> PublishJob: ...

    @abstractmethod
    def save_resume_state(self, target_id: int, state: dict | None) -> None: ...
