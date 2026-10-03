from typing import TypeVar

import aiohttp
from pydantic import BaseModel, ValidationError

from platforms2.core import AuthorizationError

from .google_response import GoogleResponse

M = TypeVar("M", bound=BaseModel)


class GoogleHttp:
    LABEL = "YouTube"

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def request(self, method: str, url: str, **kwargs) -> GoogleResponse:
        try:
            async with self._session.request(method, url, **kwargs) as response:
                return GoogleResponse(response.status, await self._body_of(response))
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise AuthorizationError(f"{self.LABEL} request failed: {type(exc).__name__}", transient=True) from None

    async def answer(self, method: str, url: str, model: type[M], **kwargs) -> M:
        response = await self.request(method, url, **kwargs)
        if not response.ok:
            raise AuthorizationError(f"{self.LABEL} refused: {response.refusal()}", transient=response.transient)
        try:
            return model.model_validate(response.body)
        except ValidationError:
            raise AuthorizationError(f"{self.LABEL} answered in an unexpected shape") from None

    @staticmethod
    async def _body_of(response: aiohttp.ClientResponse) -> dict:
        try:
            data = await response.json(content_type=None)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
