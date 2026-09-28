from abc import ABC, abstractmethod
from datetime import datetime

from ..auth.account import AccountRecord, AccountTokens
from ..auth.identity import Identity
from ..auth.tokens import TokenBundle


class AccountRepository(ABC):
    @abstractmethod
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]: ...

    @abstractmethod
    def owned_account(self, owner_id: int, account_id: int, platform: str | None = None) -> AccountRecord: ...

    @abstractmethod
    def tokens_of(self, account_id: int) -> AccountTokens: ...

    @abstractmethod
    def save_connected(
        self, owner_id: int, platform: str, bundle: TokenBundle, identity: Identity, now: datetime
    ) -> int: ...

    @abstractmethod
    def store_refreshed(
        self, account_id: int, previous_expiry: datetime | None, bundle: TokenBundle, now: datetime
    ) -> bool: ...

    @abstractmethod
    def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool: ...

    @abstractmethod
    def release_refresh_lease(self, account_id: int, until: datetime) -> None: ...

    @abstractmethod
    def mark_needs_reauth(self, account_id: int, reason: str) -> None: ...

    @abstractmethod
    def revoke(self, account_id: int) -> None: ...

    @abstractmethod
    def expiring_before(self, moment: datetime) -> list[int]: ...
