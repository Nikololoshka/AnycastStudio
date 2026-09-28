import logging

from ...core.publishing import Confirmation, NotReady, Published, Publisher, PublishJob, ReadyToCommit, TargetStatus
from ..client import LABEL
from ..options import XOptions
from ..upload import ResumeState, XUploader
from .posts import PostApi
from .status import MediaStatusApi

logger = logging.getLogger(__name__)


class XPublisher(Publisher):
    label = LABEL

    def __init__(self, uploader: XUploader, statuses: MediaStatusApi, posts: PostApi):
        self._uploader = uploader
        self._statuses = statuses
        self._posts = posts

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        media = job.draft.media
        return self._uploader.upload(
            path=job.video_path,
            size=media.size_bytes,
            mime_type=media.mime_type,
            access_token=access_token,
            resume=ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def confirm(self, job: PublishJob, access_token: str) -> Confirmation:
        status = self._statuses.fetch(access_token, job.uploaded_media_id)
        if status.is_failed:
            raise status.failure()
        if not status.is_ready:
            return NotReady()
        return ReadyToCommit()

    def commit(self, job: PublishJob, access_token: str) -> Published:
        options = XOptions.of(job.draft.settings)
        post_id = self._posts.create(access_token, job.draft.caption(), job.uploaded_media_id, options)
        logger.info("Target %s: X post %s created", job.target_id, post_id)
        return Published(TargetStatus.COMPLETED, self._posts.post_url(post_id))
