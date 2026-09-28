import logging
import random
import time

from ..errors import PlatformError

logger = logging.getLogger(__name__)


class RetryPolicy:
    BASE_BACKOFF_MS = 1_000
    MAX_BACKOFF_MS = 30_000

    def __init__(self, attempts: int):
        self.attempts = attempts

    def backoff_ms(self, attempt: int) -> int:
        ceiling = min(self.BASE_BACKOFF_MS * (2**attempt), self.MAX_BACKOFF_MS)
        return random.randint(ceiling // 2, ceiling)

    def run(self, action, *, label: str, attempts: int | None = None):
        attempts = attempts or self.attempts

        for attempt in range(attempts):
            try:
                return action()
            except PlatformError as failure:
                if not failure.retryable or attempt == attempts - 1:
                    raise
                delay = self.backoff_ms(attempt)
                logger.info("%s: %s, retrying in %d ms", label, failure.message, delay)
                time.sleep(delay / 1000)
