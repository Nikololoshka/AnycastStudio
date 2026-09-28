from ...core.upload import TokenRejectionGuard
from ..client import XClient
from ..options import XOptions
from ..responses import Created

POST_URL = "https://x.com/i/web/status/{post_id}"


class PostApi:
    def __init__(self, client: XClient):
        self._client = client

    def create(self, access_token: str, text: str, media_id: str, options: XOptions) -> str:
        body = {"text": text, "media": {"media_ids": [media_id]}, **options.as_post_fields()}
        response = TokenRejectionGuard().run(
            lambda: self._client.call("POST", "tweets", access_token, attempts=1, json=body)
        )
        return self._client.data_of(response, Created, refusal="X did not say which post it created").id

    @staticmethod
    def post_url(post_id: str) -> str:
        return POST_URL.format(post_id=post_id)
