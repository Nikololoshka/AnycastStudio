import asyncio
from datetime import UTC, datetime

from .clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
