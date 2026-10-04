from abc import ABC, abstractmethod
from datetime import datetime

from platforms.core import AuthProfile, AuthToken, PlatformType

from ..accounts.account_record import AccountRecord
from ..accounts.account_tokens import AccountTokens


class AccountRepository(ABC):
    @abstractmethod
    async def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]: ...

    @abstractmethod
    async def owned_account(
        self, owner_id: int, account_id: int, platform: PlatformType | None = None
    ) -> AccountRecord: ...

    @abstractmethod
    async def tokens_of(self, account_id: int) -> AccountTokens: ...

    @abstractmethod
    async def save_connected(
        self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile, now: datetime
    ) -> int: ...

    @abstractmethod
    async def store_refreshed(
        self, account_id: int, previous_expiry: datetime | None, token: AuthToken, now: datetime
    ) -> bool: ...

    @abstractmethod
    async def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool: ...

    @abstractmethod
    async def release_refresh_lease(self, account_id: int, until: datetime) -> None: ...

    @abstractmethod
    async def mark_needs_reauth(self, account_id: int, reason: str) -> None: ...

    @abstractmethod
    async def revoke(self, account_id: int) -> None: ...

    @abstractmethod
    async def expiring_before(self, moment: datetime) -> list[int]: ...
