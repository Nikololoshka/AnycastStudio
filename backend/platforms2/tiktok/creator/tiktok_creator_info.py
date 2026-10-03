from ..core import TikTokEndpoints, TikTokHttp
from .answers import Creator, CreatorInfo


class TikTokCreatorInfo:

    def __init__(self, http: TikTokHttp):
        self._http = http

    async def fetch(self, access_token: str) -> Creator:
        answer = await self._http.answer(
            "POST", TikTokEndpoints.CREATOR_INFO, CreatorInfo, headers=self._http.bearer(access_token)
        )
        return answer.data
