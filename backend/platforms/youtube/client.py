from ..core.http import PlatformClient

LABEL = "YouTube"


class YouTubeClient(PlatformClient):
    label = LABEL

    @staticmethod
    def bearer(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}


def client() -> YouTubeClient:
    from config import wiring

    return YouTubeClient(wiring.container().config.http)


def bearer(access_token: str) -> dict:
    return YouTubeClient.bearer(access_token)


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return client().send(method, url, attempts=attempts, **kwargs)
