from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from ..errors import NeedsFreshToken

T = TypeVar("T")


class AccessTokens(ABC):
    @abstractmethod
    def valid(self, account_id: int) -> str: ...

    @abstractmethod
    def refresh(self, account_id: int) -> str: ...

    def run(
        self,
        account_id: int,
        action: Callable[[str], T],
        on_rejected: Callable[[NeedsFreshToken], None] | None = None,
    ) -> T:
        try:
            return action(self.valid(account_id))
        except NeedsFreshToken as rejection:
            if on_rejected is not None:
                on_rejected(rejection)
            return action(self.refresh(account_id))
