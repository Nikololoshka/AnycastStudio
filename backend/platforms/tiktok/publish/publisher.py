import logging

from ...core.errors import FailureType, PlatformError
from ...core.publishing import Confirmation, NotReady, Published, Publisher, PublishJob, TargetStatus
from ..account import CreatorInfoApi
from ..client import LABEL
from ..options import TikTokOptions
from ..upload import PostInfo, ResumeState, TikTokUploader
from .status import PublishStatusApi

logger = logging.getLogger(__name__)


class TikTokPublisher(Publisher):
    label = LABEL

    def __init__(self, uploader: TikTokUploader, statuses: PublishStatusApi, creators: CreatorInfoApi):
        self._uploader = uploader
        self._statuses = statuses
        self._creators = creators

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        media = job.draft.media
        options = TikTokOptions.of(job.draft.settings)
        creator = self._creators.query(access_token)
        refusals = creator.refusals(options, media.duration_seconds)
        if refusals:
            raise PlatformError(FailureType.VALIDATION, "; ".join(refusals), details=",".join(refusals))

        return self._uploader.upload(
            path=job.video_path,
            size=media.size_bytes,
            mime_type=media.mime_type,
            post_info=PostInfo.of(job.draft, options, creator),
            access_token=access_token,
            resume=ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = self._statuses.fetch(access_token, job.uploaded_media_id)
        if status.is_failed:
            raise status.failure()
        if not status.is_complete:
            return NotReady()
        return Published(TargetStatus.COMPLETED, self._url_of(status.post_ids, access_token))

    def _url_of(self, post_ids: tuple[str, ...], access_token: str) -> str:
        if not post_ids:
            return ""
        try:
            username = self._creators.query(access_token).username
        except PlatformError as error:
            logger.info("Could not learn the TikTok username for the post link: %s", error.__class__.__name__)
            return ""
        return self._statuses.post_url(username, post_ids[0]) if username else ""
