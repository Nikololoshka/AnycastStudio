import asyncio
from collections.abc import Awaitable, Callable

from ..platform_error import PlatformError


class RetryPolicy:
    MAX_BACKOFF_SECONDS = 30

    def __init__(self, retries: int):
        self._retries = retries

    async def run[T](self, action: Callable[[], Awaitable[T]]) -> T:
        for attempt in range(self._retries):
            try:
                return await action()
            except PlatformError as error:
                if not error.transient:
                    raise
            await asyncio.sleep(min(2**attempt, self.MAX_BACKOFF_SECONDS))
        return await action()
