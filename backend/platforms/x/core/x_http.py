from platforms.core import PlatformHttp

from .x_response import XResponse


class XHttp(PlatformHttp[XResponse]):
    LABEL = "X"
    RESPONSE = XResponse
