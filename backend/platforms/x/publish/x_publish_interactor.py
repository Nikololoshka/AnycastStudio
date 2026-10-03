import logging
from collections.abc import AsyncGenerator
from functools import partial
from typing import override

import aiohttp

from platforms.core import (
    AwaitingConfirmation,
    Confirmation,
    NotReady,
    PlatformError,
    PlatformFailure,
    Published,
    PublishInteractor,
    PublishJob,
    PublishOutcome,
    ReadyToCommit,
    RetryPolicy,
    UploadProgress,
    VideoFile,
)

from ..core import XConfig, XEndpoints, XHttp
from .answers import Created, MediaStatus
from .x_options import XOptions

logger = logging.getLogger(__name__)


class XPublishInteractor(PublishInteractor):
    MEDIA_CATEGORY = "tweet_video"

    def __init__(self, config: XConfig, http: XHttp):
        self._config = config
        self._http = http
        self._retry = RetryPolicy(config.retries)

    @override
    async def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]:
        size = job.media.size_bytes
        if size <= 0:
            raise PlatformError(PlatformFailure.INVALID, "The video is empty")
        media_id = await self._initialize(job, access_token)
        video = VideoFile(job.media.path)
        yield UploadProgress(0, size)

        for index, offset in enumerate(range(0, size, self._config.segment_bytes)):
            piece = await video.piece(offset, min(self._config.segment_bytes, size - offset))
            await self._retry.run(partial(self._append, media_id, index, piece, access_token))
            yield UploadProgress(offset + len(piece), size)

        await self._http.answer(
            "POST", XEndpoints.media_finalize(media_id), Created, headers=self._http.bearer(access_token)
        )
        yield UploadProgress(size, size, media_id=media_id)

    @override
    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome:
        return AwaitingConfirmation()

    @override
    async def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = await self._http.answer(
            "GET",
            XEndpoints.MEDIA_UPLOAD,
            MediaStatus,
            headers=self._http.bearer(access_token),
            params={"command": "STATUS", "media_id": job.media_id},
        )
        processing = status.data.processing_info
        if processing.is_failed:
            raise processing.failure()
        if not processing.is_ready:
            return NotReady()
        return ReadyToCommit()

    @override
    async def commit(self, job: PublishJob, access_token: str) -> Published:
        body = {
            "text": job.draft.caption(),
            "media": {"media_ids": [job.media_id]},
            **XOptions.of(job.draft.settings).as_post_fields(),
        }
        created = await self._http.answer(
            "POST", XEndpoints.TWEETS, Created, headers=self._http.bearer(access_token), json=body
        )
        logger.info("Target %s: X post %s created", job.target_id, created.data.id)
        return Published(XEndpoints.POST.format(post_id=created.data.id))

    async def _initialize(self, job: PublishJob, access_token: str) -> str:
        body = {
            "media_type": job.media.mime_type,
            "total_bytes": job.media.size_bytes,
            "media_category": self.MEDIA_CATEGORY,
        }
        created = await self._http.answer(
            "POST", XEndpoints.MEDIA_INITIALIZE, Created, headers=self._http.bearer(access_token), json=body
        )
        return created.data.id

    async def _append(self, media_id: str, index: int, piece: bytes, access_token: str) -> None:
        form = aiohttp.FormData()
        form.add_field("segment_index", str(index))
        form.add_field("media", piece, filename="segment", content_type="application/octet-stream")
        response = await self._http.request(
            "POST", XEndpoints.media_append(media_id), headers=self._http.bearer(access_token), data=form
        )
        if not response.ok:
            raise PlatformError(response.failure(), f"X refused a segment: {response.refusal()}")
