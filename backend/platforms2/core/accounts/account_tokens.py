from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..auth import AuthToken
from ..platform_type import PlatformType
from .account_status import AccountStatus


@dataclass(frozen=True)
class AccountTokens:
    id: int
    platform: PlatformType
    status: AccountStatus
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime | None = None
    lease_until: datetime | None = None
    scopes: tuple[str, ...] = ()

    def expires_within(self, now: datetime, margin: timedelta) -> bool:
        return self.expires_at is not None and now >= self.expires_at - margin

    def stored_token(self) -> AuthToken:
        return AuthToken(access_token=self.access_token, refresh_token=self.refresh_token or None, scopes=self.scopes)
