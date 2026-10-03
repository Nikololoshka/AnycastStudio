from platforms2.core import PlatformHttp

from .tiktok_response import TikTokResponse


class TikTokHttp(PlatformHttp[TikTokResponse]):
    LABEL = "TikTok"
    RESPONSE = TikTokResponse
