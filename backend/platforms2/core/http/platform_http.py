from typing import ClassVar

import aiohttp
from pydantic import BaseModel, ValidationError

from ..auth import AuthFailure, AuthorizationError
from .platform_response import PlatformResponse


class PlatformHttp[R: PlatformResponse]:
    LABEL: ClassVar[str]
    RESPONSE: ClassVar[type[PlatformResponse]]

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    @staticmethod
    def bearer(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def request(self, method: str, url: str, **kwargs) -> R:
        try:
            async with self._session.request(method, url, **kwargs) as response:
                return self.RESPONSE(response.status, await self._body_of(response))
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise AuthorizationError(AuthFailure.NETWORK, f"{self.LABEL} request failed: {type(exc).__name__}") from None

    async def answer[M: BaseModel](self, method: str, url: str, model: type[M], **kwargs) -> M:
        response = await self.request(method, url, **kwargs)
        if not response.ok:
            raise AuthorizationError(response.failure(), f"{self.LABEL} refused: {response.refusal()}")
        try:
            return model.model_validate(response.body)
        except ValidationError:
            raise AuthorizationError(AuthFailure.UNEXPECTED, f"{self.LABEL} answered in an unexpected shape") from None

    @staticmethod
    async def _body_of(response: aiohttp.ClientResponse) -> dict:
        try:
            data = await response.json(content_type=None)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
