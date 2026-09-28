from ...core.publishing import Published, Publisher, PublishJob, TargetStatus
from ..client import LABEL
from ..options import YouTubeOptions
from ..upload import ResumeState, VideoMetadata, YouTubeUploader
from .visibility import YouTubeVisibility


class YouTubePublisher(Publisher):
    label = LABEL

    def __init__(self, uploader: YouTubeUploader, visibility: YouTubeVisibility):
        self._uploader = uploader
        self._visibility = visibility

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        options = YouTubeOptions.of(job.draft.settings)
        media = job.draft.media
        return self._uploader.upload(
            path=job.video_path,
            size=media.size_bytes,
            mime_type=media.mime_type,
            metadata=VideoMetadata.of(job, options),
            access_token=access_token,
            resume=ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def publish(self, job: PublishJob, media_id: str, access_token: str) -> Published:
        options = YouTubeOptions.of(job.draft.settings)
        if job.publish_at:
            url = self._visibility.schedule(media_id, access_token, options, job.publish_at.isoformat())
            return Published(TargetStatus.SCHEDULED, url)
        return Published(TargetStatus.COMPLETED, self._visibility.publish(media_id, access_token, options))
