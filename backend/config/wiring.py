from functools import cache, cached_property

from django.conf import settings
from django.core.signals import setting_changed

from platforms.core.auth import OAuth2Provider
from platforms.core.config import HttpConfig, OAuthCredentials, PlatformConfig, UploadConfig
from platforms.core.platform import Platform, PlatformCatalog
from platforms.core.ports import (
    AccessTokens,
    AccountRepository,
    Cache,
    Clock,
    PublicationRepository,
    SystemClock,
    TargetRepository,
    TaskQueue,
    UnitOfWork,
)
from platforms.core.publishing.commit import CommitGuard
from platforms.core.publishing.confirmation import ConfirmationPoller
from platforms.core.publishing.dispatcher import DeferredDispatcher
from platforms.core.publishing.failures import FailureMapper
from platforms.core.publishing.pipeline import PublicationPipeline
from platforms.core.publishing.service import PublicationService
from platforms.core.publishing.writer import TargetWriter
from platforms.x import XProvider
from platforms.registry import PlatformRegistry
from platforms.tiktok.account import CreatorInfoApi, CreatorInfoService
from platforms.tiktok.client import TikTokClient

CREDENTIAL_SETTINGS = {
    "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"),
    "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"),
    "instagram": ("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET"),
    "x": ("X_CLIENT_ID", "X_CLIENT_SECRET"),
}


def _credentials(id_name: str, secret_name: str) -> OAuthCredentials:
    return OAuthCredentials(
        client_id_name=id_name,
        client_secret_name=secret_name,
        client_id=getattr(settings, id_name, ""),
        client_secret=getattr(settings, secret_name, ""),
    )


class Container:
    @cached_property
    def config(self) -> PlatformConfig:
        return PlatformConfig(
            http=HttpConfig(timeout=settings.HTTP_TIMEOUT, attempts=settings.UPLOAD_RETRY_ATTEMPTS),
            upload=UploadConfig(chunk_bytes=settings.PLATFORM_CHUNK_BYTES, stall_limit=settings.UPLOAD_RETRY_ATTEMPTS),
            redirect_origin=settings.PUBLIC_REDIRECT_ORIGIN,
            credentials={name: _credentials(*names) for name, names in CREDENTIAL_SETTINGS.items()},
        )

    @cached_property
    def providers(self) -> dict[str, OAuth2Provider]:
        return {platform.name: platform.provider for platform in self.catalog.all()}

    @cached_property
    def clock(self) -> Clock:
        return SystemClock()

    @cached_property
    def catalog(self) -> PlatformCatalog:
        from publishing.publishers import PUBLISHERS

        providers = {kind.name: kind for kind in (XProvider,)}
        built = PlatformRegistry.build(self.config, self.clock).all()
        transitional = (
            Platform(
                name=name,
                label=publisher.label,
                capabilities=publisher.capabilities(),
                provider=providers[name].create(self.config),
                publisher=publisher,
                validator=publisher,
            )
            for name, publisher in PUBLISHERS.items()
        )
        return PlatformRegistry((*built, *transitional))

    @cached_property
    def targets(self) -> TargetRepository:
        from publishing.repositories import DjangoTargetRepository

        return DjangoTargetRepository()

    @cached_property
    def publication_rows(self) -> PublicationRepository:
        from publishing.repositories import DjangoPublicationRepository

        return DjangoPublicationRepository()

    @cached_property
    def accounts(self) -> AccountRepository:
        from social.repositories import DjangoAccountRepository

        return DjangoAccountRepository()

    @cached_property
    def unit_of_work(self) -> UnitOfWork:
        from common.transactions import DjangoUnitOfWork

        return DjangoUnitOfWork()

    @cached_property
    def tokens(self) -> AccessTokens:
        from social.tokens import DjangoAccessTokens

        return DjangoAccessTokens()

    @cached_property
    def queue(self) -> TaskQueue:
        from publishing.queue import CeleryTaskQueue

        return CeleryTaskQueue()

    @cached_property
    def writer(self) -> TargetWriter:
        return TargetWriter(self.targets, self.clock)

    @cached_property
    def pipeline(self) -> PublicationPipeline:
        return PublicationPipeline(self.targets, self.catalog, self.tokens, self.queue, self.writer, FailureMapper())

    @cached_property
    def confirmations(self) -> ConfirmationPoller:
        commits = CommitGuard(self.writer, self.tokens)
        return ConfirmationPoller(
            self.targets, self.catalog, self.tokens, self.queue, self.writer, FailureMapper(), commits
        )

    @cached_property
    def publications(self) -> PublicationService:
        return PublicationService(
            self.publication_rows,
            self.targets,
            self.accounts,
            self.catalog,
            self.queue,
            self.unit_of_work,
            self.clock,
        )

    @cached_property
    def cache(self) -> Cache:
        from common.caching import DjangoCache

        return DjangoCache()

    @cached_property
    def creator_info(self) -> CreatorInfoService:
        return CreatorInfoService(CreatorInfoApi(TikTokClient(self.config.http)), self.tokens, self.cache)

    @cached_property
    def dispatcher(self) -> DeferredDispatcher:
        return DeferredDispatcher(self.targets, self.catalog, self.queue, self.writer)


@cache
def container() -> Container:
    return Container()


def _forget_container(**_) -> None:
    container.cache_clear()


setting_changed.connect(_forget_container, dispatch_uid="config.wiring.forget_container")
