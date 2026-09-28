from ...core.errors import FailureType, PlatformError
from ...core.upload import TokenRejectionGuard
from ..client import RUPLOAD_ROOT, InstagramClient
from ..responses import Created
from .reel import ReelInfo
from .responses import Chunk
from .state import ResumeState


class ContainerUploadProtocol:
    def __init__(self, client: InstagramClient):
        self._client = client

    def create(self, access_token: str, ig_user_id: str, reel: ReelInfo) -> str:
        refusal = "Instagram did not open an upload"
        container = TokenRejectionGuard().run(
            lambda: self._client.call(
                "POST", f"{ig_user_id}/media", access_token, Created, refusal=refusal, attempts=1, data=reel.as_form()
            )
        )
        return container.id

    def send_piece(self, access_token: str, state: ResumeState, piece: bytes, size: int) -> None:
        headers = {
            **self._client.authorization(access_token),
            "offset": str(state.offset),
            "file_size": str(size),
        }
        url = f"{RUPLOAD_ROOT}/{state.container_id}"
        response = TokenRejectionGuard(state).run(lambda: self._client.send("POST", url, headers=headers, data=piece))
        refusal = "Instagram did not accept a piece of the video"
        if not self._client.parse(response, Chunk, refusal=refusal).success:
            raise PlatformError(FailureType.PLATFORM, refusal)
