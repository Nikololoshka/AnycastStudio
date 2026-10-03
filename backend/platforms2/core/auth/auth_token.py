from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthToken:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_in: int | None = None
    scopes: tuple[str, ...] = ()
