from ...core.errors import FailureType, PlatformError
from ...core.upload import TokenRejectionGuard
from ..client import API_ROOT, TikTokClient
from .post_info import PostInfo
from .responses import InitData
from .state import ChunkPlan

INIT_ENDPOINT = f"{API_ROOT}/post/publish/video/init/"


class DirectPostProtocol:
    def __init__(self, client: TikTokClient):
        self._client = client

    def init(self, access_token: str, post_info: PostInfo, size: int, plan: ChunkPlan) -> InitData:
        body = {
            "post_info": post_info.as_body(),
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": plan.chunk_size,
                "total_chunk_count": plan.total_chunks,
            },
        }
        refusal = "TikTok did not open an upload"
        return TokenRejectionGuard().run(
            lambda: self._client.call("POST", INIT_ENDPOINT, access_token, InitData, refusal=refusal, json=body)
        )

    def send_chunk(
        self, upload_url: str, piece: bytes, first: int, last: int, size: int, mime_type: str, is_last: bool
    ) -> None:
        headers = {"Content-Type": mime_type, "Content-Range": f"bytes {first}-{last}/{size}"}
        response = self._client.send("PUT", upload_url, headers=headers, data=piece)
        if is_last and response.status_code != 201:
            raise PlatformError(FailureType.PLATFORM, f"TikTok answered HTTP {response.status_code} to the last chunk")
