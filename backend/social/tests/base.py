"""Shared setup for the connection scenarios. The platform is always mocked."""

import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from accounts.models import User
from social.models import SocialAccount

CONNECT_URL = "/api/social/youtube/connect"
CALLBACK_URL = "/api/social/youtube/callback"
ACCOUNTS_URL = "/api/social/accounts"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"

CLIENT_SECRET = "test-client-secret-DO-NOT-LEAK"
ACCESS_TOKEN = "ya29.fake-access-token"
REFRESH_TOKEN = "1//fake-refresh-token"
CODE = "the-code"
CHANNEL_ID = "UC_fake_channel"

TOKEN_RESPONSE = {
    "access_token": ACCESS_TOKEN,
    "refresh_token": REFRESH_TOKEN,
    "expires_in": 3600,
    "scope": "https://www.googleapis.com/auth/youtube.upload",
}

CHANNEL_RESPONSE = {
    "items": [
        {
            "id": CHANNEL_ID,
            "snippet": {
                "title": "A Channel",
                "customUrl": "@a-channel",
                "thumbnails": {"default": {"url": "https://example.com/avatar.jpg"}},
            },
        }
    ]
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class SocialTestCase(TestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters
        self.user = User.objects.create_user(EMAIL, PASSWORD)
        patcher = mock.patch("platforms.http.requests.request")
        self.http = patcher.start()
        self.addCleanup(patcher.stop)
        self.given_platform_responds()

    def given_platform_responds(self, token=None, channel=None):
        """Answer the token endpoint first, then the channel endpoint."""
        self.http.side_effect = [
            FakeResponse(payload=token if token is not None else TOKEN_RESPONSE),
            FakeResponse(payload=channel if channel is not None else CHANNEL_RESPONSE),
        ]

    def sign_in(self):
        self.client.force_login(self.user)

    def body(self, response) -> dict:
        return json.loads(response.content)

    def given_started_connection(self) -> str:
        """Return the `state` the connect endpoint handed to the browser."""
        response = self.client.post(CONNECT_URL)
        auth_url = self.body(response)["authUrl"]
        return auth_url.split("state=")[1].split("&")[0]

    def callback(self, **params):
        return self.client.get(CALLBACK_URL, params)

    def only_account(self) -> SocialAccount:
        return SocialAccount.objects.get()
