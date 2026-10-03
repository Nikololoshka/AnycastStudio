from collections.abc import AsyncGenerator
from functools import partial
from typing import override

from googleapiclient.http import HttpRequest
from pydantic import ValidationError

from platforms2.core import (
    PlatformError,
    PlatformFailure,
    Published,
    PublishInteractor,
    PublishJob,
    PublishOutcome,
    Scheduled,
    UploadProgress,
)

from ..core import GoogleEndpoints, YouTubeConfig
from .answers import UploadedVideo
from .video_metadata import VideoMetadata
from .video_upload import VideoUpload
from .youtube_api import YouTubeApi
from .youtube_options import YouTubeOptions


class YouTubePublishInteractor(PublishInteractor):

    def __init__(self, config: YouTubeConfig):
        self._config = config
        self._api = YouTubeApi(config)

    @override
    async def upload(self, job: PublishJob, access_token: str) -> AsyncGenerator[UploadProgress]:
        request = await self._api.run(partial(self._insert, job, access_token))
        response = None
        while response is None:
            status, response = await self._api.run(partial(request.next_chunk, num_retries=self._config.retries))
            if status is not None:
                yield UploadProgress(status.resumable_progress, job.media.size_bytes)
        size = job.media.size_bytes
        yield UploadProgress(size, size, media_id=self._video_id_of(response))

    @override
    async def publish(self, job: PublishJob, access_token: str) -> PublishOutcome:
        options = YouTubeOptions.of(job.draft.settings)
        url = GoogleEndpoints.WATCH.format(video_id=job.media_id)
        if job.publish_at:
            visibility = {"privacyStatus": "private", "publishAt": job.publish_at.isoformat()}
            await self._update_status(job.media_id, access_token, options, visibility)
            return Scheduled(url)
        await self._update_status(job.media_id, access_token, options, {"privacyStatus": options.privacy_status})
        return Published(url)

    def _insert(self, job: PublishJob, access_token: str) -> HttpRequest:
        options = YouTubeOptions.of(job.draft.settings)
        return self._api.videos(access_token).insert(
            part="snippet,status",
            body=VideoMetadata.of(job, options).as_body(),
            notifySubscribers=options.notify_subscribers,
            media_body=VideoUpload(job.media, self._config.chunk_bytes),
        )

    async def _update_status(self, video_id: str, access_token: str, options: YouTubeOptions, visibility: dict) -> None:
        body = {"id": video_id, "status": {**options.status_fields(), **visibility}}
        await self._api.run(partial(self._update, access_token, body))

    def _update(self, access_token: str, body: dict) -> dict:
        request = self._api.videos(access_token).update(part="status", body=body)
        return request.execute(num_retries=self._config.retries)

    @staticmethod
    def _video_id_of(response: dict) -> str:
        try:
            return UploadedVideo.model_validate(response).id
        except ValidationError:
            message = "YouTube accepted the file but returned no video id"
            raise PlatformError(PlatformFailure.UNEXPECTED, message) from None
