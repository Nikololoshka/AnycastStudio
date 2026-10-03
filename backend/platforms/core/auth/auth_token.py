from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Self


@dataclass(frozen=True)
class AuthToken:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_in: int | None = None
    scopes: tuple[str, ...] = ()

    def expires_at(self, now: datetime) -> datetime | None:
        return now + timedelta(seconds=int(self.expires_in)) if self.expires_in else None

    def merged_with(self, previous: Self) -> Self:
        return replace(
            self,
            refresh_token=self.refresh_token or previous.refresh_token,
            scopes=self.scopes or previous.scopes,
        )
