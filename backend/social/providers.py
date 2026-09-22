"""Which platforms can be connected.

Adding a platform is one import and one entry: everything else — the session
lifecycle, the views, the URLs — is shared.
"""

from platforms.base import PlatformProvider, ProviderError
from platforms.youtube import YouTubeProvider

PROVIDERS: dict[str, PlatformProvider] = {
    provider.name: provider for provider in (YouTubeProvider(),)
}


def get_provider(name: str) -> PlatformProvider | None:
    return PROVIDERS.get(name)


__all__ = ["PROVIDERS", "ProviderError", "get_provider"]
