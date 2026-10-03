from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True)
class XOptions:
    REPLY_AUDIENCES: ClassVar = ("everyone", "following", "mentionedUsers", "subscribers", "verified")
    EVERYONE: ClassVar = "everyone"

    reply_audience: str = "everyone"
    made_with_ai: bool = False
    paid_partnership: bool = False
    super_followers_only: bool = False

    @classmethod
    def of(cls, raw: Mapping) -> Self:
        audience = raw.get("replyAudience")
        return cls(
            reply_audience=audience if audience in cls.REPLY_AUDIENCES else cls.EVERYONE,
            made_with_ai=raw.get("madeWithAi") is True,
            paid_partnership=raw.get("paidPartnership") is True,
            super_followers_only=raw.get("superFollowersOnly") is True,
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
        if self.reply_audience != self.EVERYONE:
            fields["reply_settings"] = self.reply_audience
        if self.made_with_ai:
            fields["made_with_ai"] = True
        if self.paid_partnership:
            fields["paid_partnership"] = True
        if self.super_followers_only:
            fields["for_super_followers_only"] = True
        return fields
