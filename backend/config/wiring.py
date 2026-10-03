from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import cache, cached_property

import aiohttp
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.signals import setting_changed

from platforms2 import PlatformCatalog, PlatformConfigs
from platforms2.core.ports import (
    AccountRepository,
    Cache,
    Clock,
    OAuthSessionRepository,
    PublicationRepository,
    SystemClock,
    TargetRepository,
    TaskQueue,
)
from platforms2.core.usecases.accounts import AccountService, ConnectFlow, TokenService
from platforms2.core.usecases.publications import (
    CommitGuard,
    ConfirmationPoller,
    DeferredDispatcher,
    PublicationPipeline,
    PublicationService,
    StaleTargetSweeper,
    TargetWriter,
)
from platforms2.instagram import InstagramConfig
from platforms2.tiktok import TikTokConfig
from platforms2.tiktok.core import TikTokHttp
from platforms2.tiktok.creator import CreatorInfoService, TikTokCreatorInfo
from platforms2.x import XConfig
from platforms2.youtube import YouTubeConfig

CALLBACK_PATH = "/api/social/{platform}/callback"
X_MAX_SEGMENT_BYTES = 4 * 1024**2


class Services:
    def __init__(self, container: "Container", session: aiohttp.ClientSession):
        clock = container.clock
        self.catalog = PlatformCatalog(container.platform_configs, session)
        self.tokens = TokenService(container.accounts, self.catalog, clock)
        self.account_service = AccountService(container.accounts, self.catalog, clock)
        self.connect_flow = ConnectFlow(
            container.oauth_sessions,
            self.account_service,
            self.catalog,
            clock,
            timedelta(seconds=settings.OAUTH_SESSION_TTL),
        )
        writer = TargetWriter(container.targets, clock)
        self.pipeline = PublicationPipeline(container.targets, self.catalog, self.tokens, container.queue, writer)
        self.confirmations = ConfirmationPoller(
            container.targets,
            self.catalog,
            self.tokens,
            container.queue,
            writer,
            CommitGuard(writer, self.tokens, self.catalog),
        )
        self.publications = PublicationService(
            container.publication_rows, container.targets, container.accounts, self.catalog, container.queue, clock
        )
        self.dispatcher = DeferredDispatcher(container.targets, self.catalog, container.queue, writer)
        self.sweeper = StaleTargetSweeper(container.targets, clock)
        self.creator_info = CreatorInfoService(TikTokCreatorInfo(TikTokHttp(session)), self.tokens, container.cache)


class Container:
    @cached_property
    def platform_configs(self) -> PlatformConfigs:
        chunk_bytes = settings.PLATFORM_CHUNK_BYTES
        retries = settings.UPLOAD_RETRY_ATTEMPTS
        return PlatformConfigs(
            youtube=YouTubeConfig(
                client_id=settings.YOUTUBE_CLIENT_ID,
                client_secret=settings.YOUTUBE_CLIENT_SECRET,
                redirect_uri=self._callback_url("youtube"),
                chunk_bytes=chunk_bytes,
                retries=retries,
                http_timeout=settings.HTTP_TIMEOUT,
            ),
            tiktok=TikTokConfig(
                client_key=settings.TIKTOK_CLIENT_KEY,
                client_secret=settings.TIKTOK_CLIENT_SECRET,
                redirect_uri=self._callback_url("tiktok"),
                chunk_bytes=chunk_bytes,
                retries=retries,
            ),
            instagram=InstagramConfig(
                client_id=settings.INSTAGRAM_CLIENT_ID,
                client_secret=settings.INSTAGRAM_CLIENT_SECRET,
                redirect_uri=self._callback_url("instagram"),
                chunk_bytes=chunk_bytes,
                retries=retries,
            ),
            x=XConfig(
                client_id=settings.X_CLIENT_ID,
                client_secret=settings.X_CLIENT_SECRET,
                redirect_uri=self._callback_url("x"),
                segment_bytes=min(chunk_bytes, X_MAX_SEGMENT_BYTES),
                retries=retries,
            ),
        )

    @staticmethod
    def _callback_url(platform: str) -> str:
        return f"{settings.PUBLIC_REDIRECT_ORIGIN}{CALLBACK_PATH.format(platform=platform)}"

    @cached_property
    def clock(self) -> Clock:
        return SystemClock()

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
    def oauth_sessions(self) -> OAuthSessionRepository:
        from social.repositories import DjangoOAuthSessionRepository

        return DjangoOAuthSessionRepository()

    @cached_property
    def queue(self) -> TaskQueue:
        from publishing.queue import CeleryTaskQueue

        return CeleryTaskQueue()

    @cached_property
    def cache(self) -> Cache:
        from common.caching import DjangoCache

        return DjangoCache()

    def open_session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(sock_connect=settings.HTTP_TIMEOUT, sock_read=settings.HTTP_TIMEOUT)
        return aiohttp.ClientSession(timeout=timeout)

    @asynccontextmanager
    async def services(self) -> AsyncIterator[Services]:
        async with self.open_session() as session:
            yield Services(self, session)

    def run[T](self, work: Callable[[Services], Awaitable[T]]) -> T:
        async def scoped() -> T:
            async with self.services() as services:
                return await work(services)

        return async_to_sync(scoped)()


@cache
def container() -> Container:
    return Container()


def _forget_container(**_) -> None:
    container.cache_clear()


setting_changed.connect(_forget_container, dispatch_uid="config.wiring.forget_container")
