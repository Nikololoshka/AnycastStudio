from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .tokens import TokenBundle


class AccountStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    REVOKED = "revoked"


@dataclass(frozen=True)
class AccountRecord:
    id: int
    platform: str
    status: AccountStatus


@dataclass(frozen=True)
class AccountTokens:
    id: int
    platform: str
    status: AccountStatus
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime | None = None
    lease_until: datetime | None = None
    scopes: tuple[str, ...] = ()

    def expires_within(self, now: datetime, margin: timedelta) -> bool:
        if not self.expires_at:
            return False
        return now >= self.expires_at - margin

    def stored_bundle(self) -> TokenBundle:
        return TokenBundle(access_token=self.access_token, refresh_token=self.refresh_token, scopes=self.scopes)
