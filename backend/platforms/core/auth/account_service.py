import logging

from ..errors import ProviderError
from ..platform import PlatformCatalog
from ..ports import AccountRepository, Clock
from .identity import Identity
from .tokens import TokenBundle

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, accounts: AccountRepository, catalog: PlatformCatalog, clock: Clock):
        self._accounts = accounts
        self._catalog = catalog
        self._clock = clock

    def save(self, owner_id: int, platform: str, bundle: TokenBundle, identity: Identity) -> int:
        account_id = self._accounts.save_connected(owner_id, platform, bundle, identity, self._clock.now())
        logger.info("Connected %s account %s for user %s", platform, account_id, owner_id)
        return account_id

    def disconnect(self, account_id: int) -> None:
        account = self._accounts.tokens_of(account_id)
        if account.platform in self._catalog.names() and (account.access_token or account.refresh_token):
            provider = self._catalog.get(account.platform).provider
            try:
                provider.revoke(account.access_token, account.refresh_token)
            except ProviderError as error:
                logger.info("Revoking %s account %s failed: %s", account.platform, account_id, error.message)

        self._accounts.revoke(account_id)
        logger.info("Disconnected %s account %s", account.platform, account_id)
