from abc import ABC, abstractmethod

from ..auth.account import AccountRecord


class AccountRepository(ABC):
    @abstractmethod
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]: ...
