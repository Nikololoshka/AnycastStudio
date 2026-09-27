from dataclasses import dataclass

from ..http import AUTHENTICATION, FILE, PLATFORM, VALIDATION, PlatformFailure
from ..upload import fresh_token_on_rejection
from .api import API_ROOT, call

STATUS_ENDPOINT = f"{API_ROOT}/post/publish/status/fetch/"

COMPLETE_STATUSES = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")
FAILED_STATUS = "FAILED"

FAIL_REASONS = {
    "file_format_check_failed": (FILE, "TikTok rejected the video format"),
    "duration_check_failed": (FILE, "The video duration is outside TikTok's allowed range"),
    "frame_rate_check_failed": (FILE, "The video frame rate is outside TikTok's allowed range"),
    "picture_size_check_failed": (FILE, "The video resolution is outside TikTok's allowed range"),
    "video_pull_failed": (PLATFORM, "TikTok could not read the uploaded video"),
    "publish_cancelled": (PLATFORM, "The publish was cancelled on TikTok"),
    "spam_risk_too_many_posts": (PLATFORM, "TikTok blocked the publish: daily post limit reached"),
    "spam_risk_user_banned_from_posting": (PLATFORM, "TikTok blocked the publish: the account cannot post"),
    "spam_risk_text": (VALIDATION, "TikTok flagged the caption as spam"),
    "spam_risk": (PLATFORM, "TikTok flagged the publish as spam"),
    "user_cancel": (PLATFORM, "The publish was cancelled by the user on TikTok"),
    "auth_removed": (AUTHENTICATION, "The TikTok authorization was revoked; reconnect the account"),
    "unaudited_client_can_only_post_to_private_accounts": (
        VALIDATION,
        "This TikTok app is not audited yet and can only post to private accounts",
    ),
    "privacy_level_check_failed": (VALIDATION, "TikTok rejected the selected privacy level"),
    "internal": (PLATFORM, "TikTok failed on its side; publish again later"),
}


@dataclass(frozen=True)
class PublishStatus:
    status: str
    fail_reason: str = ""
    post_ids: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.status in COMPLETE_STATUSES

    @property
    def is_failed(self) -> bool:
        return self.status == FAILED_STATUS


def fetch(access_token: str, publish_id: str) -> PublishStatus:
    data = fresh_token_on_rejection(
        lambda: call("POST", STATUS_ENDPOINT, access_token, json={"publish_id": publish_id})
    )

    post_ids = data.get("publicaly_available_post_id") or ()
    return PublishStatus(
        status=str(data.get("status") or ""),
        fail_reason=str(data.get("fail_reason") or ""),
        post_ids=tuple(str(post_id) for post_id in post_ids),
    )


def failure_of(fail_reason: str) -> PlatformFailure:
    kind, message = FAIL_REASONS.get(fail_reason, (PLATFORM, "TikTok refused to publish the video"))
    return PlatformFailure(kind, message, details=fail_reason)


def post_url(username: str, post_id: str) -> str:
    return f"https://www.tiktok.com/@{username}/video/{post_id}"
