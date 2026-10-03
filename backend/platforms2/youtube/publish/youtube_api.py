import asyncio
import json
from collections.abc import Callable

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import build_http

from platforms2.core import PlatformError, PlatformFailure

from ..core import GoogleResponse, YouTubeConfig


class YouTubeApi:

    def __init__(self, config: YouTubeConfig):
        self._config = config

    def videos(self, access_token: str) -> Resource:
        transport = build_http()
        transport.timeout = self._config.http_timeout
        http = AuthorizedHttp(Credentials(token=access_token), http=transport, refresh_status_codes=())
        return build("youtube", "v3", http=http, static_discovery=True, cache_discovery=False).videos()

    async def run[T](self, call: Callable[[], T]) -> T:
        try:
            return await asyncio.to_thread(call)
        except HttpError as error:
            response = GoogleResponse(error.resp.status, self._body_of(error))
            raise PlatformError(response.failure(), f"YouTube refused: {response.refusal()}") from None
        except FileNotFoundError:
            message = "The uploaded video is no longer on the server"
            raise PlatformError(PlatformFailure.MEDIA_MISSING, message) from None
        except (httplib2.HttpLib2Error, OSError) as error:
            raise PlatformError(PlatformFailure.NETWORK, f"YouTube request failed: {type(error).__name__}") from None

    @staticmethod
    def _body_of(error: HttpError) -> dict:
        try:
            body = json.loads(error.content)
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}
