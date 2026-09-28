import logging

from ...core.errors import PlatformError
from ...core.publishing import Confirmation, NotReady, Published, Publisher, PublishJob, TargetStatus
from ..client import LABEL
from ..upload import InstagramUploader, ReelInfo, ResumeState
from .status import ContainerApi

logger = logging.getLogger(__name__)


class InstagramPublisher(Publisher):
    label = LABEL

    def __init__(self, uploader: InstagramUploader, containers: ContainerApi):
        self._uploader = uploader
        self._containers = containers

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        return self._uploader.upload(
            path=job.video_path,
            size=job.draft.media.size_bytes,
            ig_user_id=job.external_id,
            reel=ReelInfo.of(job.draft),
            access_token=access_token,
            resume=ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = self._containers.status(access_token, job.uploaded_media_id)
        if status.is_published:
            return Published(TargetStatus.COMPLETED)
        if status.is_dead:
            raise status.failure()
        if not status.is_ready:
            return NotReady()

        media_id = self._published_media_id(job, access_token)
        if media_id is None:
            return NotReady()
        return Published(TargetStatus.COMPLETED, self._url_of(media_id, access_token))

    def _published_media_id(self, job: PublishJob, access_token: str) -> str | None:
        try:
            return self._containers.publish(access_token, job.external_id, job.uploaded_media_id)
        except PlatformError as failure:
            if failure.retryable:
                logger.info("Target %s: Instagram publish did not answer, asking again later", job.target_id)
                return None
            raise

    def _url_of(self, media_id: str, access_token: str) -> str:
        try:
            return self._containers.post_url(access_token, media_id)
        except PlatformError as failure:
            logger.info("Could not learn the Instagram post link: %s", failure.type)
            return ""
