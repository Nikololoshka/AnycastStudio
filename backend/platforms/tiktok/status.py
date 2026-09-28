from pydantic import Field

from ..core.errors import FailureType, PlatformError
from ..core.http import PlatformModel
from ..core.upload import TokenRejectionGuard
from .client import API_ROOT, call

STATUS_ENDPOINT = f"{API_ROOT}/post/publish/status/fetch/"

COMPLETE_STATUSES = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")
FAILED_STATUS = "FAILED"

FAIL_REASONS = {
    "file_format_check_failed": (FailureType.FILE, "TikTok rejected the video format"),
    "duration_check_failed": (FailureType.FILE, "The video duration is outside TikTok's allowed range"),
    "frame_rate_check_failed": (FailureType.FILE, "The video frame rate is outside TikTok's allowed range"),
    "picture_size_check_failed": (FailureType.FILE, "The video resolution is outside TikTok's allowed range"),
    "video_pull_failed": (FailureType.PLATFORM, "TikTok could not read the uploaded video"),
    "publish_cancelled": (FailureType.PLATFORM, "The publish was cancelled on TikTok"),
    "spam_risk_too_many_posts": (FailureType.PLATFORM, "TikTok blocked the publish: daily post limit reached"),
    "spam_risk_user_banned_from_posting": (FailureType.PLATFORM, "TikTok blocked the publish: the account cannot post"),
    "spam_risk_text": (FailureType.VALIDATION, "TikTok flagged the caption as spam"),
    "spam_risk": (FailureType.PLATFORM, "TikTok flagged the publish as spam"),
    "user_cancel": (FailureType.PLATFORM, "The publish was cancelled by the user on TikTok"),
    "auth_removed": (FailureType.AUTHENTICATION, "The TikTok authorization was revoked; reconnect the account"),
    "unaudited_client_can_only_post_to_private_accounts": (
        FailureType.VALIDATION,
        "This TikTok app is not audited yet and can only post to private accounts",
    ),
    "privacy_level_check_failed": (FailureType.VALIDATION, "TikTok rejected the selected privacy level"),
    "internal": (FailureType.PLATFORM, "TikTok failed on its side; publish again later"),
}


class PublishStatus(PlatformModel):
    status: str = ""
    fail_reason: str = ""
    post_ids: tuple[str, ...] = Field((), alias="publicaly_available_post_id")

    @property
    def is_complete(self) -> bool:
        return self.status in COMPLETE_STATUSES

    @property
    def is_failed(self) -> bool:
        return self.status == FAILED_STATUS


def fetch_status(access_token: str, publish_id: str) -> PublishStatus:
    return TokenRejectionGuard().run(
        lambda: call("POST", STATUS_ENDPOINT, access_token, PublishStatus, json={"publish_id": publish_id})
    )


def failure_of(fail_reason: str) -> PlatformError:
    kind, message = FAIL_REASONS.get(fail_reason, (FailureType.PLATFORM, "TikTok refused to publish the video"))
    return PlatformError(kind, message, details=fail_reason)


def post_url(username: str, post_id: str) -> str:
    return f"https://www.tiktok.com/@{username}/video/{post_id}"
