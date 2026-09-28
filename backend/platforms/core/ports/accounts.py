from abc import ABC, abstractmethod

from ..auth.account import AccountRecord


class AccountRepository(ABC):
    @abstractmethod
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]: ...

    @abstractmethod
    def owned_account(self, owner_id: int, account_id: int, platform: str) -> AccountRecord: ...
