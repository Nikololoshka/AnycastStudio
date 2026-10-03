import logging
from collections.abc import AsyncGenerator
from functools import partial
from typing import override

from platforms2.core import (
    AwaitingConfirmation,
    Confirmation,
    NotReady,
    PlatformError,
    PlatformFailure,
    Published,
    PublishInteractor,
    PublishJob,
    PublishOutcome,
    RetryPolicy,
    UploadProgress,
    VideoFile,
)

from ..instagram_config import InstagramConfig
from ..instagram_endpoints import InstagramEndpoints
from ..instagram_http import InstagramHttp
from .chunk_answer import ChunkAnswer
from .container_status import ContainerStatus
from .created import Created
from .permalink import Permalink
from .reel_info import ReelInfo

logger = logging.getLogger(__name__)


class InstagramPublishInteractor(PublishInteractor):

    def __init__(self, config: InstagramConfig, http: InstagramHttp):
        self._config = config
        self._http = http
        self._retry = RetryPolicy(config.retries)

    @override
    async def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]:
        size = job.media.size_bytes
        if size <= 0:
            raise PlatformError(PlatformFailure.INVALID, "The video is empty")
        container_id = await self._create_container(job, access_token)
        video = VideoFile(job.media.path)
        yield UploadProgress(0, size)

        offset = 0
        while offset < size:
            piece = await video.piece(offset, min(self._config.chunk_bytes, size - offset))
            await self._retry.run(partial(self._send_piece, container_id, piece, offset, size, access_token))
            offset += len(piece)
            yield UploadProgress(offset, size, media_id=container_id if offset >= size else None)

    @override
    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome:
        return AwaitingConfirmation()

    @override
    async def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = await self._http.answer(
            "GET",
            InstagramEndpoints.node(job.media_id),
            ContainerStatus,
            headers=self._http.authorization(access_token),
            params={"fields": "status_code,status"},
        )
        if status.is_published:
            return Published()
        if status.is_dead:
            raise status.failure()
        if not status.is_ready:
            return NotReady()

        try:
            media_id = await self._publish_container(job, access_token)
        except PlatformError as error:
            if not error.transient:
                raise
            logger.info("Target %s: Instagram publish did not answer, asking again later", job.target_id)
            return NotReady()
        return Published(await self._url_of(media_id, access_token))

    async def _create_container(self, job: PublishJob, access_token: str) -> str:
        created = await self._http.answer(
            "POST",
            InstagramEndpoints.media(job.external_id),
            Created,
            headers=self._http.authorization(access_token),
            data=ReelInfo.of(job.draft).as_form(),
        )
        return created.id

    async def _send_piece(self, container_id: str, piece: bytes, offset: int, size: int, access_token: str) -> None:
        headers = {**self._http.authorization(access_token), "offset": str(offset), "file_size": str(size)}
        answer = await self._http.answer(
            "POST", InstagramEndpoints.rupload(container_id), ChunkAnswer, headers=headers, data=piece
        )
        if not answer.success:
            raise PlatformError(PlatformFailure.REFUSED, "Instagram did not accept a piece of the video")

    async def _publish_container(self, job: PublishJob, access_token: str) -> str:
        published = await self._http.answer(
            "POST",
            InstagramEndpoints.media_publish(job.external_id),
            Created,
            headers=self._http.authorization(access_token),
            data={"creation_id": job.media_id},
        )
        return published.id

    async def _url_of(self, media_id: str, access_token: str) -> str:
        try:
            answer = await self._http.answer(
                "GET",
                InstagramEndpoints.node(media_id),
                Permalink,
                headers=self._http.authorization(access_token),
                params={"fields": "permalink"},
            )
        except PlatformError as error:
            logger.info("Could not learn the Instagram post link: %s", error.failure)
            return ""
        return answer.permalink
