import logging
import random
import time

from django.conf import settings

from .failures import PlatformFailure, classify

logger = logging.getLogger(__name__)

BASE_BACKOFF_MS = 1_000
MAX_BACKOFF_MS = 30_000


def backoff_ms(attempt: int) -> int:
    ceiling = min(BASE_BACKOFF_MS * (2**attempt), MAX_BACKOFF_MS)
    return random.randint(ceiling // 2, ceiling)


def with_retry(send, *, label: str, attempts: int | None = None):
    attempts = attempts or settings.UPLOAD_RETRY_ATTEMPTS

    for attempt in range(attempts):
        try:
            response = send()
        except PlatformFailure as network_failure:
            failure = network_failure
        else:
            failure = classify(response, label)
            if failure is None:
                return response

        if not failure.retryable or attempt == attempts - 1:
            raise failure

        delay = backoff_ms(attempt)
        logger.info("%s: %s, retrying in %d ms", label, failure.message, delay)
        time.sleep(delay / 1000)
