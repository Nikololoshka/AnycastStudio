from typing import ClassVar

from pydantic import Field

from platforms.core import PlatformError, PlatformFailure

from ...core import TikTokAnswer


class Status(TikTokAnswer):
    COMPLETE: ClassVar = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")
    FAILED: ClassVar = "FAILED"
    FAIL_REASONS: ClassVar = {
        "file_format_check_failed": (PlatformFailure.FILE_REJECTED, "TikTok rejected the video format"),
        "duration_check_failed": (PlatformFailure.FILE_REJECTED, "The video duration is outside TikTok's range"),
        "frame_rate_check_failed": (PlatformFailure.FILE_REJECTED, "The video frame rate is outside TikTok's range"),
        "picture_size_check_failed": (PlatformFailure.FILE_REJECTED, "The video resolution is outside TikTok's range"),
        "video_pull_failed": (PlatformFailure.REFUSED, "TikTok could not read the uploaded video"),
        "publish_cancelled": (PlatformFailure.REFUSED, "The publish was cancelled on TikTok"),
        "spam_risk_too_many_posts": (PlatformFailure.RATE_LIMITED, "TikTok blocked the publish: daily post limit"),
        "spam_risk_user_banned_from_posting": (PlatformFailure.REFUSED, "TikTok blocked the account from posting"),
        "spam_risk_text": (PlatformFailure.INVALID, "TikTok flagged the caption as spam"),
        "spam_risk": (PlatformFailure.REFUSED, "TikTok flagged the publish as spam"),
        "user_cancel": (PlatformFailure.REFUSED, "The publish was cancelled by the user on TikTok"),
        "auth_removed": (PlatformFailure.GRANT_REVOKED, "The TikTok authorization was revoked; reconnect the account"),
        "unaudited_client_can_only_post_to_private_accounts": (
            PlatformFailure.INVALID,
            "This TikTok app is not audited yet and can only post to private accounts",
        ),
        "privacy_level_check_failed": (PlatformFailure.INVALID, "TikTok rejected the selected privacy level"),
        "internal": (PlatformFailure.REFUSED, "TikTok failed on its side; publish again later"),
    }

    status: str = ""
    fail_reason: str = ""
    post_ids: tuple[int, ...] = Field((), alias="publicaly_available_post_id")

    @property
    def is_complete(self) -> bool:
        return self.status in self.COMPLETE

    @property
    def is_failed(self) -> bool:
        return self.status == self.FAILED

    def failure(self) -> PlatformError:
        fallback = (PlatformFailure.REFUSED, "TikTok refused to publish the video")
        failure, message = self.FAIL_REASONS.get(self.fail_reason, fallback)
        return PlatformError(failure, message, details=self.fail_reason)


class PublishStatus(TikTokAnswer):
    data: Status
