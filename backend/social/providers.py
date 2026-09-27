from platforms.instagram import InstagramProvider
from platforms.oauth import PlatformProvider
from platforms.tiktok import TikTokProvider
from platforms.x import XProvider
from platforms.youtube import YouTubeProvider

PROVIDERS: dict[str, PlatformProvider] = {
    provider.name: provider for provider in (YouTubeProvider(), TikTokProvider(), InstagramProvider(), XProvider())
}
