from platforms.core import PlatformHttp

from .tiktok_response import TikTokResponse


class TikTokHttp(PlatformHttp[TikTokResponse]):
    LABEL = "TikTok"
    RESPONSE = TikTokResponse
