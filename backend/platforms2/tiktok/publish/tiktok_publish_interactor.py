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

from ..tiktok_config import TikTokConfig
from ..tiktok_endpoints import TikTokEndpoints
from ..tiktok_http import TikTokHttp
from .chunk_plan import ChunkPlan
from .creator_info import Creator, CreatorInfo
from .post_info import PostInfo
from .publish_status import PublishStatus
from .tiktok_options import TikTokOptions
from .video_init import Upload, VideoInit

logger = logging.getLogger(__name__)


class TikTokPublishInteractor(PublishInteractor):
    LAST_CHUNK_STATUS = 201

    def __init__(self, config: TikTokConfig, http: TikTokHttp):
        self._config = config
        self._http = http
        self._retry = RetryPolicy(config.retries)

    @override
    async def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]:
        size = job.media.size_bytes
        plan = ChunkPlan.of(size, self._config.chunk_bytes)
        upload = await self._init(job, access_token, plan)
        video = VideoFile(job.media.path)
        yield UploadProgress(0, size)

        for index in range(plan.total_chunks):
            first, last = plan.bounds_of(index)
            is_last = index == plan.total_chunks - 1
            piece = await video.piece(first, last - first + 1)
            await self._retry.run(partial(self._send_chunk, upload.upload_url, piece, first, last, job, is_last))
            yield UploadProgress(last + 1, size, media_id=upload.publish_id if is_last else None)

    @override
    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome:
        return AwaitingConfirmation()

    @override
    async def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        answer = await self._http.answer(
            "POST",
            TikTokEndpoints.PUBLISH_STATUS,
            PublishStatus,
            headers=self._http.bearer(access_token),
            json={"publish_id": job.media_id},
        )
        status = answer.data
        if status.is_failed:
            raise status.failure()
        if not status.is_complete:
            return NotReady()
        return Published(await self._url_of(status.post_ids, access_token))

    async def _init(self, job: PublishJob, access_token: str, plan: ChunkPlan) -> Upload:
        options = TikTokOptions.of(job.draft.settings)
        creator = await self._creator(access_token)
        refusals = creator.refusals(options, job.media.duration_seconds)
        if refusals:
            raise PlatformError(PlatformFailure.INVALID, "; ".join(refusals), details=",".join(refusals))
        post_info = PostInfo.of(job.draft, options, creator)
        answer = await self._http.answer(
            "POST",
            TikTokEndpoints.VIDEO_INIT,
            VideoInit,
            headers=self._http.bearer(access_token),
            json={"post_info": post_info.as_body(), "source_info": plan.as_source_info()},
        )
        return answer.data

    async def _creator(self, access_token: str) -> Creator:
        answer = await self._http.answer(
            "POST", TikTokEndpoints.CREATOR_INFO, CreatorInfo, headers=self._http.bearer(access_token)
        )
        return answer.data

    async def _send_chunk(
        self, upload_url: str, piece: bytes, first: int, last: int, job: PublishJob, is_last: bool
    ) -> None:
        headers = {"Content-Type": job.media.mime_type, "Content-Range": f"bytes {first}-{last}/{job.media.size_bytes}"}
        response = await self._http.request("PUT", upload_url, headers=headers, data=piece)
        if not response.ok or (is_last and response.status != self.LAST_CHUNK_STATUS):
            raise PlatformError(response.failure(), f"TikTok refused the chunk: {response.refusal()}")

    async def _url_of(self, post_ids: tuple[int, ...], access_token: str) -> str:
        if not post_ids:
            return ""
        try:
            username = (await self._creator(access_token)).username
        except PlatformError as error:
            logger.info("Could not learn the TikTok username for the post link: %s", error.failure)
            return ""
        return TikTokEndpoints.POST.format(username=username, post_id=post_ids[0]) if username else ""
