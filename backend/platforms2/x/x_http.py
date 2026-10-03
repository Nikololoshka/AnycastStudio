from platforms2.core import PlatformHttp

from .x_response import XResponse


class XHttp(PlatformHttp[XResponse]):
    LABEL = "X"
    RESPONSE = XResponse
