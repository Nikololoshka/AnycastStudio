from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from ..platform_error import PlatformError
from ..platform_failure import PlatformFailure


class AccessTokens(ABC):
    @abstractmethod
    async def valid(self, account_id: int) -> str: ...

    @abstractmethod
    async def refresh(self, account_id: int) -> str: ...

    async def run[T](self, account_id: int, action: Callable[[str], Awaitable[T]]) -> T:
        try:
            return await action(await self.valid(account_id))
        except PlatformError as error:
            if error.failure is not PlatformFailure.TOKEN_REJECTED:
                raise
        return await action(await self.refresh(account_id))
