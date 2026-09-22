"""What every platform must provide, and nothing more.

This package is deliberately not a Django app. It is the counterpart of the
frontend's src/platforms: one folder per platform, no imports between them,
and no dependency on the models, so a task can use it directly.

Authorising an account and publishing a video are separate jobs with separate
lifetimes, so they are separate protocols. Only the first one exists today.
"""

from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    """A platform refused us. `message` is safe to show the person."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def merged_with(self, previous: "TokenBundle | None") -> "TokenBundle":
        """Keep the previous refresh token when the platform did not send a new one.

        Google omits it on refresh; X and TikTok rotate it. Dropping it would
        silently turn a long-lived connection into a one-hour one.
        """
        if self.refresh_token or previous is None:
            return self
        return TokenBundle(
            access_token=self.access_token,
            refresh_token=previous.refresh_token,
            expires_in=self.expires_in,
            scopes=self.scopes or previous.scopes,
        )


@dataclass(frozen=True)
class Capabilities:
    """What a platform supports. The browser uses it to adapt the composer."""

    label: str
    scheduling: str  # native | stagedPublish | deferredUpload | unsupported
    title: bool
    description: bool
    hashtags: bool
    drafts: bool
    max_file_size: int | None = None
    supported_mime_types: tuple[str, ...] = field(default_factory=tuple)

    def as_json(self) -> dict:
        return {
            "label": self.label,
            "scheduling": self.scheduling,
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
            "drafts": self.drafts,
            "maxFileSize": self.max_file_size,
            "supportedMimeTypes": list(self.supported_mime_types),
        }


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Identity:
    """Who the token belongs to, in the platform's own terms."""

    external_id: str
    display_name: str
    avatar_url: str = ""
    extra: dict = field(default_factory=dict)


class PlatformProvider(Protocol):
    name: str
    scopes: tuple[str, ...]
    uses_pkce: bool

    @property
    def redirect_uri(self) -> str: ...

    def authorize_url(self, state: str, code_challenge: str | None) -> str: ...

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle: ...

    def refresh(self, refresh_token: str) -> TokenBundle: ...

    def fetch_identity(self, access_token: str) -> Identity: ...

    def revoke(self, token: str) -> None: ...
