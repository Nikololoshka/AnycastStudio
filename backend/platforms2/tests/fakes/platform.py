from collections.abc import AsyncGenerator

from platforms2.core import (
    AuthorizationInteractor,
    AuthProfile,
    AuthRequest,
    AuthToken,
    Confirmation,
    NotReady,
    Platform,
    PlatformCapabilities,
    PlatformType,
    PlatformValidator,
    PublishDraft,
    Published,
    PublishInteractor,
    PublishJob,
    PublishMedia,
    PublishOutcome,
    Scheduling,
    UploadProgress,
    ValidationResult,
)
from platforms2.core.platform_registry import PlatformRegistry

FAKE = PlatformType.TIKTOK
CAPABILITIES = PlatformCapabilities(
    label="Fake", scheduling=Scheduling.DEFERRED_UPLOAD, title=True, description=True, hashtags=True, drafts=False
)


class FakeAuthorization(AuthorizationInteractor):
    def __init__(self):
        self.refreshes: list[str] = []
        self.refresh_answer: AuthToken | Exception = AuthToken("fresh", expires_in=3600)
        self.exchange_answer: AuthToken | Exception = AuthToken("first", "refresh-1", 3600)
        self.exchanged: list[tuple[str, str]] = []
        self.revoked: list[AuthToken] = []
        self.revoke_failure: Exception | None = None

    def create_auth_request(self, state: str) -> AuthRequest:
        return AuthRequest(f"https://fake.test/authorize?state={state}&code_challenge=c", state, "the-verifier")

    async def create_auth_token(self, code: str, code_verifier: str) -> AuthToken:
        self.exchanged.append((code, code_verifier))
        if isinstance(self.exchange_answer, Exception):
            raise self.exchange_answer
        return self.exchange_answer

    async def refresh_auth_token(self, refresh_token: str) -> AuthToken:
        self.refreshes.append(refresh_token)
        if isinstance(self.refresh_answer, Exception):
            raise self.refresh_answer
        return self.refresh_answer

    async def fetch_auth_profile(self, access_token: str) -> AuthProfile:
        return AuthProfile(external_id="fake-1", display_name="A Creator")

    async def revoke_auth_token(self, token: AuthToken) -> None:
        self.revoked.append(token)
        if self.revoke_failure is not None:
            raise self.revoke_failure


class FakePublishing(PublishInteractor):
    def __init__(self):
        self.outcome: PublishOutcome = Published("https://fake.test/1")
        self.confirmations: list[Confirmation | Exception] = []
        self.commit_outcome: Published | Exception = Published("https://fake.test/post")
        self.commits = 0
        self.uncertain: Published | None = None
        self.upload_failures: list[Exception] = []
        self.tokens_seen: list[str] = []
        self.chunks = 4
        self.on_chunk = None

    async def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]:
        self.tokens_seen.append(access_token)
        if self.upload_failures:
            raise self.upload_failures.pop(0)
        size = job.media.size_bytes
        for chunk in range(1, self.chunks + 1):
            if self.on_chunk is not None:
                self.on_chunk(chunk)
            yield UploadProgress(size * chunk // self.chunks, size)
        yield UploadProgress(size, size, media_id="media-1")

    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome:
        return self.outcome

    async def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        if not self.confirmations:
            return NotReady()
        confirmation = self.confirmations.pop(0)
        if isinstance(confirmation, Exception):
            raise confirmation
        return confirmation

    async def commit(self, job: PublishJob, access_token: str) -> Published:
        self.commits += 1
        if isinstance(self.commit_outcome, Exception):
            raise self.commit_outcome
        return self.commit_outcome

    async def resolve_uncertain(self, job: PublishJob, access_token: str) -> Published | None:
        return self.uncertain


class FakeValidator(PlatformValidator):
    def __init__(self):
        self.errors: tuple[str, ...] = ()

    def validate(self, draft: PublishDraft, media: PublishMedia) -> ValidationResult:
        return ValidationResult(self.errors)


class FakePlatform(Platform):
    platform_type = FAKE

    def __init__(self):
        self.configured = True
        self.capabilities = CAPABILITIES
        self.validator = FakeValidator()
        self.authorization = FakeAuthorization()
        self.publishing = FakePublishing()

    def get_authorization_interactor(self) -> AuthorizationInteractor:
        return self.authorization

    def get_publish_interactor(self) -> PublishInteractor:
        return self.publishing


class FakeRegistry(PlatformRegistry):
    def __init__(self, platform: FakePlatform):
        self.platform = platform

    def get(self, platform_type: PlatformType) -> Platform:
        if platform_type != FAKE:
            raise KeyError(platform_type)
        return self.platform

    def all(self) -> tuple[Platform, ...]:
        return (self.platform,)
