from abc import ABC, abstractmethod
from datetime import datetime

from ..auth.session import OAuthSessionRecord, OAuthSessionStatus


class OAuthSessionRepository(ABC):
    @abstractmethod
    def sweep_created_before(self, moment: datetime) -> int: ...

    @abstractmethod
    def create(self, owner_id: int, platform: str, state: str, code_verifier: str) -> OAuthSessionRecord: ...

    @abstractmethod
    def claim(self, platform: str, state: str, created_after: datetime) -> OAuthSessionRecord | None: ...

    @abstractmethod
    def finish(self, session_id: int, status: OAuthSessionStatus) -> None: ...
