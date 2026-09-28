from config.wiring import container
from platforms.core.auth import OAuth2Provider


def providers() -> dict[str, OAuth2Provider]:
    return container().providers
