from platforms.core import PlatformHttp

from .google_response import GoogleResponse


class GoogleHttp(PlatformHttp[GoogleResponse]):
    LABEL = "YouTube"
    RESPONSE = GoogleResponse
