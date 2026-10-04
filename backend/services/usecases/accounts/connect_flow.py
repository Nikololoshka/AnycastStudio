import logging
import secrets
from datetime import timedelta

from platforms.core import PlatformError, PlatformRegistry, PlatformType

from ...core.accounts.connect_outcome import ConnectOutcome
from ...core.accounts.oauth_session_record import OAuthSessionRecord
from ...core.accounts.oauth_session_status import OAuthSessionStatus
from ...core.domain import NotFound, Unavailable
from ...core.ports import Clock, OAuthSessionRepository
from .account_service import AccountService

logger = logging.getLogger(__name__)


class ConnectFlow:
    STATE_BYTES = 32

    def __init__(
        self,
        sessions: OAuthSessionRepository,
        accounts: AccountService,
        platforms: PlatformRegistry,
        clock: Clock,
        session_ttl: timedelta,
    ):
        self._sessions = sessions
        self._accounts = accounts
        self._platforms = platforms
        self._clock = clock
        self._session_ttl = session_ttl

    async def start(self, owner_id: int, platform_name: str) -> str:
        platform_type = self._type_of(platform_name)
        if platform_type is None:
            raise NotFound()
        platform = self._platforms.get(platform_type)
        if not platform.configured:
            logger.error("Cannot start %s sign-in: its client credentials are not configured", platform_type)
            raise Unavailable(f"{platform.capabilities.label} is not configured")

        await self._sweep_expired()
        request = platform.get_authorization_interactor().create_auth_request(secrets.token_urlsafe(self.STATE_BYTES))
        session = await self._sessions.create_pending(owner_id, platform_type, request.state, request.code_verifier)
        logger.info("OAuth session %s started for %s", session.id, platform_type)
        return request.url

    async def complete(
        self, platform_name: str, state: str, code: str | None, refused: bool, requester_id: int | None
    ) -> ConnectOutcome:
        platform_type = self._type_of(platform_name)
        if platform_type is None or not state:
            return ConnectOutcome.INVALID

        created_after = self._clock.now() - self._session_ttl
        session = await self._sessions.claim_pending_by_state(platform_type, state, created_after)
        if session is None:
            return ConnectOutcome.INVALID

        if session.owner_id != requester_id:
            await self._finish(session, OAuthSessionStatus.ERROR)
            logger.warning("OAuth session %s was opened by a different session", session.id)
            return ConnectOutcome.INVALID

        if refused or not code:
            await self._finish(session, OAuthSessionStatus.ERROR)
            return ConnectOutcome.CANCELLED

        authorization = self._platforms.get(platform_type).get_authorization_interactor()
        try:
            token = await authorization.create_auth_token(code, session.code_verifier)
            profile = await authorization.fetch_auth_profile(token.access_token)
        except PlatformError as error:
            await self._finish(session, OAuthSessionStatus.ERROR)
            logger.info("OAuth session %s failed: %s (%s)", session.id, error.message, error.failure)
            return ConnectOutcome.FAILED
        except Exception:
            logger.exception("OAuth session %s: unexpected error", session.id)
            await self._finish(session, OAuthSessionStatus.ERROR)
            return ConnectOutcome.FAILED

        await self._accounts.save(session.owner_id, platform_type, token, profile)
        await self._finish(session, OAuthSessionStatus.DONE)
        return ConnectOutcome.CONNECTED

    @staticmethod
    def _type_of(platform_name: str) -> PlatformType | None:
        try:
            return PlatformType(platform_name)
        except ValueError:
            return None

    async def _sweep_expired(self) -> None:
        deleted = await self._sessions.delete_created_before(self._clock.now() - self._session_ttl)
        if deleted:
            logger.info("Removed %d expired OAuth sessions", deleted)

    async def _finish(self, session: OAuthSessionRecord, status: OAuthSessionStatus) -> None:
        await self._sessions.mark_finished(session.id, status)
        logger.info("OAuth session %s finished as %s", session.id, status)
