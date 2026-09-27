import logging
import time

from platforms import x
from platforms.capabilities import ValidationResult
from platforms.http import NETWORK, PLATFORM, PlatformFailure
from platforms.upload import NeedsFreshToken

from ..models import PublicationTarget
from .outcome import Published, awaiting_confirmation
from .publisher import Publisher

logger = logging.getLogger(__name__)

Status = PublicationTarget.Status

POSTING_STARTED = "posting_started"
UNANSWERED = (NETWORK, PLATFORM)


def _posting_started(target: PublicationTarget) -> float | None:
    state = target.resume_state or {}
    return state.get(POSTING_STARTED)


def _set_resume_state(target: PublicationTarget, state: dict) -> None:
    PublicationTarget.objects.filter(pk=target.pk).update(resume_state=state)
    target.resume_state = state


def _mark_posting(target: PublicationTarget) -> dict:
    before = dict(target.resume_state or {})
    _set_resume_state(target, {**before, POSTING_STARTED: time.time()})
    return before


def _maybe_posted(details: str = "") -> PlatformFailure:
    return PlatformFailure(PLATFORM, "The post may have been created; check X before publishing again", details=details)


class XPublisher(Publisher):
    platform = x

    def validate(self, target: PublicationTarget) -> ValidationResult:
        asset = target.publication.asset
        return x.validate(
            caption=self.caption(target),
            size_bytes=asset.size_bytes,
            mime_type=asset.mime_type,
            duration_seconds=asset.duration_seconds,
        )

    def upload(
        self, target: PublicationTarget, access_token: str, resume: dict | None, on_progress, should_cancel
    ) -> str:
        asset = target.publication.asset
        return x.upload(
            path=self.file_of(target),
            size=asset.size_bytes,
            mime_type=asset.mime_type,
            access_token=access_token,
            resume=x.ResumeState.of(resume),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    def publish(self, target: PublicationTarget, media_id: str, access_token: str) -> Published:
        started = _posting_started(target)
        if started is None:
            return awaiting_confirmation()
        return awaiting_confirmation(**{POSTING_STARTED: started})

    def _post(self, target: PublicationTarget, access_token: str) -> str:
        before = _mark_posting(target)
        options = x.video_options_of(target.settings)
        try:
            return x.create_post(access_token, self.caption(target), target.uploaded_media_id, options)
        except NeedsFreshToken:
            _set_resume_state(target, before)
            raise
        except PlatformFailure as failure:
            if failure.type not in UNANSWERED:
                _set_resume_state(target, before)
                raise
            raise _maybe_posted(failure.details) from None

    def confirm(self, target: PublicationTarget, access_token: str) -> Published | None:
        if _posting_started(target) is not None:
            raise _maybe_posted()

        status = x.fetch_status(access_token, target.uploaded_media_id)
        if status.is_failed:
            raise x.failure_of(status)
        if not status.is_ready:
            return None

        post_id = self._post(target, access_token)
        logger.info("Target %s: X post %s created", target.pk, post_id)
        return Published(Status.COMPLETED, x.post_url(post_id))
