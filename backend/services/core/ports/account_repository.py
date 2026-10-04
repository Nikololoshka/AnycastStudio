from abc import ABC, abstractmethod
from datetime import datetime

from platforms.core import AuthProfile, AuthToken, PlatformType

from ..accounts.account_record import AccountRecord
from ..accounts.account_tokens import AccountTokens


class AccountRepository(ABC):
    @abstractmethod
    async def get_connected_accounts(self, owner_id: int) -> dict[int, AccountRecord]: ...

    @abstractmethod
    async def get_connected_account(self, owner_id: int, account_id: int) -> AccountRecord: ...

    @abstractmethod
    async def get_account_tokens(self, account_id: int) -> AccountTokens: ...

    @abstractmethod
    async def upsert_connected_account(
        self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile, now: datetime
    ) -> int: ...

    @abstractmethod
    async def save_refreshed_tokens(self, account_id: int, token: AuthToken, now: datetime) -> None: ...

    @abstractmethod
    async def try_lock_token_refresh(self, account_id: int, now: datetime, until: datetime) -> bool: ...

    @abstractmethod
    async def unlock_token_refresh(self, account_id: int, until: datetime) -> None: ...

    @abstractmethod
    async def mark_needs_reauth(self, account_id: int, reason: str) -> None: ...

    @abstractmethod
    async def clear_tokens_and_mark_revoked(self, account_id: int) -> None: ...

    @abstractmethod
    async def find_active_expiring_before(self, moment: datetime) -> list[int]: ...
