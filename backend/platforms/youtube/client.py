from ..core.http import PlatformClient

LABEL = "YouTube"
GOOGLE_LABEL = "Google"


class YouTubeClient(PlatformClient):
    label = LABEL

    @staticmethod
    def bearer(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}
