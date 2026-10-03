from platforms2.core import PlatformHttp

from .instagram_response import InstagramResponse


class InstagramHttp(PlatformHttp[InstagramResponse]):
    LABEL = "Instagram"
    RESPONSE = InstagramResponse

    @staticmethod
    def authorization(access_token: str) -> dict:
        return {"Authorization": f"OAuth {access_token}"}
