import logging
import secrets
from datetime import timedelta

from ..errors import NotFound, ProviderError, Unavailable
from ..platform import PlatformCatalog
from ..ports import Clock, OAuthSessionRepository
from .account_service import AccountService
from .pkce import Pkce
from .provider import OAuth2Provider
from .session import ConnectOutcome, OAuthSessionRecord, OAuthSessionStatus

logger = logging.getLogger(__name__)

STATE_BYTES = 32


class ConnectFlow:
    def __init__(
        self,
        sessions: OAuthSessionRepository,
        accounts: AccountService,
        catalog: PlatformCatalog,
        clock: Clock,
        session_ttl: timedelta,
    ):
        self._sessions = sessions
        self._accounts = accounts
        self._catalog = catalog
        self._clock = clock
        self._session_ttl = session_ttl

    def start(self, owner_id: int, platform: str) -> str:
        provider = self._provider_of(platform)
        if provider is None:
            raise NotFound()

        self._sweep_expired()
        verifier = Pkce.generate().verifier if provider.uses_pkce else ""
        state = secrets.token_urlsafe(STATE_BYTES)
        session = self._sessions.create(owner_id, platform, state, verifier)
        logger.info("OAuth session %s started for %s", session.id, platform)

        try:
            return provider.authorize_url(state, provider.code_challenge(verifier) if verifier else None)
        except ProviderError as error:
            self._finish(session, OAuthSessionStatus.ERROR)
            logger.error("Cannot start %s sign-in: %s", platform, error.message)
            raise Unavailable(error.message) from None

    def complete(
        self, platform: str, state: str, code: str | None, refused: bool, requester_id: int | None
    ) -> ConnectOutcome:
        provider = self._provider_of(platform)
        if provider is None:
            return ConnectOutcome.INVALID

        session = self._claim(platform, state)
        if session is None:
            return ConnectOutcome.INVALID

        if session.owner_id != requester_id:
            self._finish(session, OAuthSessionStatus.ERROR)
            logger.warning("OAuth session %s was opened by a different session", session.id)
            return ConnectOutcome.INVALID

        if refused or not code:
            self._finish(session, OAuthSessionStatus.ERROR)
            return ConnectOutcome.CANCELLED

        try:
            bundle = provider.exchange_code(code, session.code_verifier or None)
            identity = provider.fetch_identity(bundle.access_token)
        except ProviderError as error:
            self._finish(session, OAuthSessionStatus.ERROR)
            logger.info("OAuth session %s failed: %s", session.id, error.message)
            return ConnectOutcome.FAILED
        except Exception:
            logger.exception("OAuth session %s: unexpected error", session.id)
            self._finish(session, OAuthSessionStatus.ERROR)
            return ConnectOutcome.FAILED

        self._accounts.save(session.owner_id, provider.name, bundle, identity)
        self._finish(session, OAuthSessionStatus.DONE)
        return ConnectOutcome.CONNECTED

    def _provider_of(self, platform: str) -> OAuth2Provider | None:
        if platform not in self._catalog.names():
            return None
        return self._catalog.get(platform).provider

    def _claim(self, platform: str, state: str) -> OAuthSessionRecord | None:
        if not state:
            return None
        return self._sessions.claim(platform, state, self._clock.now() - self._session_ttl)

    def _sweep_expired(self) -> None:
        deleted = self._sessions.sweep_created_before(self._clock.now() - self._session_ttl)
        if deleted:
            logger.info("Removed %d expired OAuth sessions", deleted)

    def _finish(self, session: OAuthSessionRecord, status: OAuthSessionStatus) -> None:
        self._sessions.finish(session.id, status)
        logger.info("OAuth session %s finished as %s", session.id, status)
