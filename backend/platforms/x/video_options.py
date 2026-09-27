from dataclasses import dataclass

REPLY_AUDIENCES = ("everyone", "following", "mentionedUsers", "subscribers", "verified")
EVERYONE = "everyone"

MAX_TEXT_LENGTH = 280


@dataclass(frozen=True)
class VideoOptions:
    reply_audience: str = EVERYONE
    made_with_ai: bool = False
    paid_partnership: bool = False
    super_followers_only: bool = False

    def as_json(self) -> dict:
        return {
            "replyAudience": self.reply_audience,
            "madeWithAi": self.made_with_ai,
            "paidPartnership": self.paid_partnership,
            "superFollowersOnly": self.super_followers_only,
        }

    def as_post_fields(self) -> dict:
        fields: dict = {}
        if self.reply_audience != EVERYONE:
            fields["reply_settings"] = self.reply_audience
        if self.made_with_ai:
            fields["made_with_ai"] = True
        if self.paid_partnership:
            fields["paid_partnership"] = True
        if self.super_followers_only:
            fields["for_super_followers_only"] = True
        return fields


def _flag(raw: dict, key: str) -> bool:
    value = raw.get(key)
    return value if isinstance(value, bool) else False


def video_options_of(raw) -> VideoOptions:
    raw = raw if isinstance(raw, dict) else {}
    audience = raw.get("replyAudience")
    return VideoOptions(
        reply_audience=audience if audience in REPLY_AUDIENCES else EVERYONE,
        made_with_ai=_flag(raw, "madeWithAi"),
        paid_partnership=_flag(raw, "paidPartnership"),
        super_followers_only=_flag(raw, "superFollowersOnly"),
    )


def caption_of(title: str, description: str, hashtags: list[str]) -> str:
    tags = " ".join(f"#{tag}" for tag in hashtags)
    return "\n\n".join(part for part in (title.strip(), description.strip(), tags) if part)


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
