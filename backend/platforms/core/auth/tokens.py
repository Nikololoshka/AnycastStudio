from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..http import PlatformModel


@dataclass(frozen=True)
class TokenBundle:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_in: int | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def expires_at(self, now: datetime) -> datetime | None:
        if not self.expires_in:
            return None
        return now + timedelta(seconds=int(self.expires_in))

    def merged_with(self, previous: "TokenBundle | None") -> "TokenBundle":
        if self.refresh_token or previous is None:
            return self
        return TokenBundle(
            access_token=self.access_token,
            refresh_token=previous.refresh_token,
            expires_in=self.expires_in,
            scopes=self.scopes or previous.scopes,
        )


class TokenAnswer(PlatformModel):
    access_token: str = ""
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str = ""
    error: str | dict = ""
    error_description: str = ""

    @property
    def refusal_reason(self) -> str:
        if self.error_description:
            return self.error_description
        if isinstance(self.error, dict):
            return str(self.error.get("message") or "")
        return self.error

    def scopes(self, separator: str) -> tuple[str, ...]:
        return tuple(scope.strip() for scope in self.scope.split(separator) if scope.strip())
