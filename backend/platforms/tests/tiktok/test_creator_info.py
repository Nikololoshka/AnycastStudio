from platforms.core import PlatformError, PlatformFailure
from platforms.core.accounts import AccountRecord, AccountStatus
from platforms.core.domain import AccountNeedsReauth, Unavailable
from platforms.tiktok.creator import CreatorInfoService
from platforms.tiktok.creator.answers import Creator

from ..core.test_account_scenarios import AccountScenarioBase
from ..fakes.accounts import FakeCache
from ..fakes.platform import FAKE


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
        self.service = CreatorInfoService(self.creator_info, self.tokens, FakeCache())
        self.given_account()

    async def test_the_creator_info_is_asked_once_and_kept(self):
        account = AccountRecord(7, FAKE, AccountStatus.ACTIVE)

        first = await self.service.info(account)
        second = await self.service.info(account)

        self.assertEqual(first["username"], "creator")
        self.assertEqual(first["privacyLevelOptions"], ["SELF_ONLY"])
        self.assertEqual(second, first)
        self.assertEqual(self.creator_info.calls, 1)

    async def test_an_account_that_must_reconnect_is_not_asked_about(self):
        with self.assertRaises(AccountNeedsReauth):
            await self.service.info(AccountRecord(7, FAKE, AccountStatus.NEEDS_REAUTH))

        self.assertEqual(self.creator_info.calls, 0)

    async def test_a_revoked_grant_asks_for_reconnection(self):
        self.creator_info.failure = PlatformError(PlatformFailure.GRANT_REVOKED, "auth removed")

        with self.assertRaises(AccountNeedsReauth):
            await self.service.info(AccountRecord(7, FAKE, AccountStatus.ACTIVE))

    async def test_an_outage_is_unavailable(self):
        self.creator_info.failure = PlatformError(PlatformFailure.NETWORK, "down")

        with self.assertRaises(Unavailable):
            await self.service.info(AccountRecord(7, FAKE, AccountStatus.ACTIVE))
