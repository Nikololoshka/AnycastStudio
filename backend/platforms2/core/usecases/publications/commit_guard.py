from functools import partial

from ...platform_error import PlatformError
from ...platform_failure import PlatformFailure
from ...platform_registry import PlatformRegistry
from ...ports import AccessTokens
from ...publish import PublishJob, Published
from .target_writer import TargetWriter


class CommitGuard:
    COMMIT_STARTED = "commit_started"
    UNANSWERED = (PlatformFailure.NETWORK, PlatformFailure.UNEXPECTED)

    def __init__(self, writer: TargetWriter, tokens: AccessTokens, platforms: PlatformRegistry):
        self._writer = writer
        self._tokens = tokens
        self._platforms = platforms

    @classmethod
    def was_started(cls, job: PublishJob) -> bool:
        return cls.COMMIT_STARTED in job.confirmation_state

    async def resolve(self, job: PublishJob) -> Published:
        publishing = self._platforms.get(job.platform).get_publish_interactor()
        resolved = await self._tokens.run(job.account_id, partial(publishing.resolve_uncertain, job))
        if resolved is None:
            raise self._maybe_published(job)
        return resolved

    async def commit(self, job: PublishJob) -> Published:
        publishing = self._platforms.get(job.platform).get_publish_interactor()
        before = dict(job.confirmation_state)

        async def attempt(access_token: str) -> Published:
            started = {**before, self.COMMIT_STARTED: self._writer.now().isoformat()}
            await self._writer.set(job.target_id, confirmation_state=started)
            try:
                return await publishing.commit(job, access_token)
            except PlatformError as error:
                if error.failure in self.UNANSWERED:
                    raise self._maybe_published(job, error.message) from None
                await self._writer.set(job.target_id, confirmation_state=before)
                raise

        return await self._tokens.run(job.account_id, attempt)

    def _maybe_published(self, job: PublishJob, details: str = "") -> PlatformError:
        label = self._platforms.get(job.platform).capabilities.label
        message = f"The post may have been created; check {label} before publishing again"
        return PlatformError(PlatformFailure.UNCONFIRMED, message, details=details)
