from ..errors import FailureType, MaybePublished, NeedsFreshToken, PlatformError
from ..ports import AccessTokens
from .job import PublishJob
from .outcome import Published
from .publisher import Publisher
from .writer import TargetWriter

COMMIT_STARTED = "commit_started"
UNANSWERED = (FailureType.NETWORK, FailureType.PLATFORM)


class CommitGuard:
    def __init__(self, writer: TargetWriter, tokens: AccessTokens):
        self._writer = writer
        self._tokens = tokens

    @staticmethod
    def marker_of(job: PublishJob) -> dict:
        state = job.resume_state or {}
        return {COMMIT_STARTED: state[COMMIT_STARTED]} if COMMIT_STARTED in state else {}

    def was_started(self, job: PublishJob) -> bool:
        return bool(self.marker_of(job))

    def resolve(self, job: PublishJob, publisher: Publisher) -> Published:
        resolved = self._tokens.run(job.account_id, lambda token: publisher.resolve_uncertain(job, token))
        if resolved is None:
            raise MaybePublished(publisher.label)
        return resolved

    def commit(self, job: PublishJob, publisher: Publisher) -> Published:
        before = dict(job.resume_state or {})

        def attempt(access_token: str) -> Published:
            self._writer.set(job.target_id, resume_state={**before, COMMIT_STARTED: self._writer.now().isoformat()})
            try:
                return publisher.commit(job, access_token)
            except NeedsFreshToken:
                self._writer.set(job.target_id, resume_state=before)
                raise
            except PlatformError as failure:
                if failure.type not in UNANSWERED:
                    self._writer.set(job.target_id, resume_state=before)
                    raise
                raise MaybePublished(publisher.label, failure.details) from None

        return self._tokens.run(job.account_id, attempt)
