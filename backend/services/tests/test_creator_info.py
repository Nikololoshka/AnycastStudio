from platforms.core import PlatformError, PlatformFailure, PlatformType
from platforms.tiktok.creator.answers import Creator
from services.core.accounts import AccountStatus
from services.core.domain import AccountNeedsReauth, NotFound, Unavailable
from services.usecases.tiktok import CreatorInfoService

from .fakes.accounts import FakeCache
from .test_account_scenarios import AccountScenarioBase


class FakeCreatorInfo:
    def __init__(self):
        self.calls = 0
        self.failure: PlatformError | None = None

    async def fetch(self, access_token: str) -> Creator:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return Creator(creator_username="creator", privacy_level_options=("SELF_ONLY",))


class CreatorInfoScenarios(AccountScenarioBase):
    def setUp(self):
        super().setUp()
        self.creator_info = FakeCreatorInfo()
        self.service = CreatorInfoService(self.accounts, self.creator_info, self.tokens, FakeCache())

    async def test_the_creator_info_is_asked_once_and_kept(self):
        self.given_account()

        first = await self.service.info(1, 7)
        second = await self.service.info(1, 7)

        self.assertEqual(first["username"], "creator")
        self.assertEqual(first["privacyLevelOptions"], ["SELF_ONLY"])
        self.assertEqual(second, first)
        self.assertEqual(self.creator_info.calls, 1)

    async def test_an_account_of_another_platform_is_not_found(self):
        self.given_account(platform=PlatformType.YOUTUBE)

        with self.assertRaises(NotFound):
            await self.service.info(1, 7)

        self.assertEqual(self.creator_info.calls, 0)

    async def test_an_account_that_must_reconnect_is_not_asked_about(self):
        self.given_account(status=AccountStatus.NEEDS_REAUTH)

        with self.assertRaises(AccountNeedsReauth):
            await self.service.info(1, 7)

        self.assertEqual(self.creator_info.calls, 0)

    async def test_a_revoked_grant_asks_for_reconnection(self):
        self.given_account()
        self.creator_info.failure = PlatformError(PlatformFailure.GRANT_REVOKED, "auth removed")

        with self.assertRaises(AccountNeedsReauth):
            await self.service.info(1, 7)

    async def test_an_outage_is_unavailable(self):
        self.given_account()
        self.creator_info.failure = PlatformError(PlatformFailure.NETWORK, "down")

        with self.assertRaises(Unavailable):
            await self.service.info(1, 7)
