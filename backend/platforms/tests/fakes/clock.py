from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from platforms.core.ports import Clock

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FakeClock(Clock):
    def __init__(self, now: datetime = START):
        self.current = now
        self.on_sleep: Callable[[], None] | None = None

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    async def sleep(self, seconds: float) -> None:
        self.advance(timedelta(seconds=seconds))
        if self.on_sleep is not None:
            self.on_sleep()
