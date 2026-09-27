from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def merged_with(self, previous: "TokenBundle | None") -> "TokenBundle":
        if self.refresh_token or previous is None:
            return self
        return TokenBundle(
            access_token=self.access_token,
            refresh_token=previous.refresh_token,
            expires_in=self.expires_in,
            scopes=self.scopes or previous.scopes,
        )
