from ...core.upload import TokenRejectionGuard
from ..client import XClient
from ..responses import Created
from .state import ResumeState

MEDIA_CATEGORY = "tweet_video"


class MediaUploadProtocol:
    def __init__(self, client: XClient):
        self._client = client

    def initialize(self, access_token: str, size: int, mime_type: str) -> str:
        body = {"media_type": mime_type, "total_bytes": size, "media_category": MEDIA_CATEGORY}
        response = TokenRejectionGuard().run(
            lambda: self._client.call("POST", "media/upload/initialize", access_token, attempts=1, json=body)
        )
        return self._client.data_of(response, Created, refusal="X did not open an upload").id

    def append(self, access_token: str, state: ResumeState, piece: bytes) -> None:
        TokenRejectionGuard(state).run(
            lambda: self._client.call(
                "POST",
                f"media/upload/{state.media_id}/append",
                access_token,
                data={"segment_index": str(state.next_segment)},
                files={"media": ("segment", piece, "application/octet-stream")},
            )
        )

    def finalize(self, access_token: str, state: ResumeState) -> None:
        TokenRejectionGuard(state).run(
            lambda: self._client.call("POST", f"media/upload/{state.media_id}/finalize", access_token, attempts=1)
        )
