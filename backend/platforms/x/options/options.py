from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

REPLY_AUDIENCES = ("everyone", "following", "mentionedUsers", "subscribers", "verified")
EVERYONE = "everyone"


@dataclass(frozen=True)
class XOptions:
    reply_audience: str = EVERYONE
    made_with_ai: bool = False
    paid_partnership: bool = False
    super_followers_only: bool = False

    @classmethod
    def of(cls, raw) -> Self:
        raw = raw if isinstance(raw, Mapping) else {}
        audience = raw.get("replyAudience")
        return cls(
            reply_audience=audience if audience in REPLY_AUDIENCES else EVERYONE,
            made_with_ai=cls._flag(raw, "madeWithAi"),
            paid_partnership=cls._flag(raw, "paidPartnership"),
            super_followers_only=cls._flag(raw, "superFollowersOnly"),
        )

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

    @staticmethod
    def _flag(raw: Mapping, key: str) -> bool:
        value = raw.get(key)
        return value if isinstance(value, bool) else False
