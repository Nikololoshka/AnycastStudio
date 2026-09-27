from media import storage
from platforms import youtube
from platforms.capabilities import ValidationResult

from ..models import PublicationTarget
from .outcome import Published

Status = PublicationTarget.Status

capabilities = youtube.capabilities


def validate(target: PublicationTarget) -> ValidationResult:
    publication = target.publication
    asset = publication.asset
    return youtube.validate(
        title=publication.title,
        description=publication.description,
        size_bytes=asset.size_bytes,
        mime_type=asset.mime_type,
    )


def _privacy_at_upload(target: PublicationTarget, options: youtube.VideoOptions) -> str:
    return "private" if target.publication.publish_at else options.privacy_status


def _metadata(target: PublicationTarget, options: youtube.VideoOptions) -> youtube.VideoMetadata:
    publication = target.publication
    return youtube.VideoMetadata(
        title=publication.title,
        description=youtube.description_with_hashtags(
            publication.description, list(publication.hashtags), options
        ),
        tags=list(publication.hashtags),
        privacy_status=_privacy_at_upload(target, options),
        category_id=options.category_id,
        license=options.license,
        embeddable=options.embeddable,
        public_stats_viewable=options.public_stats_viewable,
        made_for_kids=options.made_for_kids,
        contains_synthetic_media=options.contains_synthetic_media,
        notify_subscribers=options.notify_subscribers,
    )


def upload(target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel) -> str:
    asset = target.publication.asset
    options = youtube.video_options_of(target.settings)
    return youtube.upload(
        path=storage.absolute(asset.storage_path),
        size=asset.size_bytes,
        mime_type=asset.mime_type,
        metadata=_metadata(target, options),
        access_token=access_token,
        resume=youtube.ResumeState.of(resume),
        on_progress=lambda uploaded, total, state: on_progress(uploaded, total, state.as_dict()),
        should_cancel=should_cancel,
    )


def publish(target: PublicationTarget, video_id: str, access_token: str) -> Published:
    options = youtube.video_options_of(target.settings)
    publish_at = target.publication.publish_at
    if publish_at:
        url = youtube.schedule(video_id, access_token, options, publish_at.isoformat())
        return Published(Status.SCHEDULED, url)
    return Published(Status.COMPLETED, youtube.publish(video_id, access_token, options))
