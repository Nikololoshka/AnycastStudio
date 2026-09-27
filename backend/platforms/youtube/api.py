from .. import http

LABEL = "YouTube"


def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}


def send(method: str, url: str, *, attempts: int | None = None, **kwargs):
    return http.send(method, url, label=LABEL, attempts=attempts, **kwargs)
