from abc import ABC, abstractmethod
from datetime import datetime

from ..accounts.oauth_session_record import OAuthSessionRecord
from ..accounts.oauth_session_status import OAuthSessionStatus
from ..platform_type import PlatformType


class OAuthSessionRepository(ABC):
    @abstractmethod
    async def sweep_created_before(self, moment: datetime) -> int: ...

    @abstractmethod
    async def create(
        self, owner_id: int, platform: PlatformType, state: str, code_verifier: str
    ) -> OAuthSessionRecord: ...

    @abstractmethod
    async def claim(self, platform: PlatformType, state: str, created_after: datetime) -> OAuthSessionRecord | None: ...

    @abstractmethod
    async def finish(self, session_id: int, status: OAuthSessionStatus) -> None: ...
