import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from accounts.models import User
from config.wiring import Container, container
from platforms2.tests.fakes.http import FakeAnswer, FakeSession
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


class SocialTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(EMAIL, PASSWORD)
        self.http = FakeSession()
        patcher = mock.patch.object(Container, "open_session", return_value=self.http)
        patcher.start()
        self.addCleanup(patcher.stop)
        sleeper = mock.patch("platforms2.core.http.retry_policy.asyncio.sleep", new=mock.AsyncMock())
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.given_platform_responds()

    def given_answers(self, *answers) -> None:
        self.http.answer_only(*answers)

    def given_platform_responds(self, token=None, channel=None):
        self.given_answers(
            FakeAnswer(200, token if token is not None else TOKEN_RESPONSE),
            FakeAnswer(200, channel if channel is not None else CHANNEL_RESPONSE),
        )

    def valid_token(self, account_id: int) -> str:
        return container().run(lambda services: services.tokens.valid(account_id))

    def refreshed_token(self, account_id: int) -> str:
        return container().run(lambda services: services.tokens.refresh(account_id))

    def refresh_expiring(self) -> int:
        return container().run(lambda services: services.tokens.refresh_expiring())

    def sign_in(self):
        self.client.force_login(self.user)

    def body(self, response) -> dict:
        return json.loads(response.content)

    def given_started_connection(self) -> str:
        response = self.client.post(CONNECT_URL)
        auth_url = self.body(response)["authUrl"]
        return auth_url.split("state=")[1].split("&")[0]

    def callback(self, **params):
        return self.client.get(CALLBACK_URL, params)

    def only_account(self) -> SocialAccount:
        return SocialAccount.objects.get()
