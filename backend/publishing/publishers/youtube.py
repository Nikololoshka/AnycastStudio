from platforms import youtube
from platforms.core.capabilities import ValidationResult
from platforms.core.publishing import PublicationDraft, PublishJob, Published, TargetStatus

from .publisher import AppPublisher


def _privacy_at_upload(job: PublishJob, options: youtube.VideoOptions) -> str:
    return "private" if job.publish_at else options.privacy_status


def _metadata(job: PublishJob, options: youtube.VideoOptions) -> youtube.VideoMetadata:
    draft = job.draft
    return youtube.VideoMetadata(
        title=draft.title,
        description=youtube.description_with_hashtags(draft.description, list(draft.hashtags), options),
        tags=list(draft.hashtags),
        privacy_status=_privacy_at_upload(job, options),
        category_id=options.category_id,
        license=options.license,
        embeddable=options.embeddable,
        public_stats_viewable=options.public_stats_viewable,
        made_for_kids=options.made_for_kids,
        contains_synthetic_media=options.contains_synthetic_media,
        notify_subscribers=options.notify_subscribers,
    )


class YouTubePublisher(AppPublisher):
    platform = youtube

    def validate(self, draft: PublicationDraft) -> ValidationResult:
        return youtube.validate(
            title=draft.title,
            description=draft.description,
            size_bytes=draft.media.size_bytes,
            mime_type=draft.media.mime_type,
        )

    def upload(self, job: PublishJob, access_token: str, on_progress, should_cancel) -> str:
        options = youtube.video_options_of(job.draft.settings)
        return youtube.upload(
            path=job.video_path,
            size=job.draft.media.size_bytes,
            mime_type=job.draft.media.mime_type,
            metadata=_metadata(job, options),
            access_token=access_token,
            resume=youtube.ResumeState.of(job.resume_state),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def publish(self, job: PublishJob, media_id: str, access_token: str) -> Published:
        options = youtube.video_options_of(job.draft.settings)
        if job.publish_at:
            url = youtube.schedule(media_id, access_token, options, job.publish_at.isoformat())
            return Published(TargetStatus.SCHEDULED, url)
        return Published(TargetStatus.COMPLETED, youtube.publish(media_id, access_token, options))
