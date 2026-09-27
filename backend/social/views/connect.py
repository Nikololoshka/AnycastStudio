import logging

from common.access import require_auth, require_post
from common.rate_limit import rate_limit
from common.responses import api_response
from platforms.oauth import ProviderError

from .. import sessions
from ..providers import PROVIDERS

logger = logging.getLogger(__name__)


@require_post
@require_auth
@rate_limit("connect")
def social_connect(request, platform: str):
    provider = PROVIDERS.get(platform)
    if provider is None:
        return api_response("not_found")

    session, challenge = sessions.create(request.user, provider)

    try:
        auth_url = provider.authorize_url(session.state, challenge)
    except ProviderError as error:
        sessions.finish(session, sessions.Status.ERROR)
        logger.error("Cannot start %s sign-in: %s", provider.name, error.message)
        return api_response("server_error", message=error.message)

    return api_response("ok", authUrl=auth_url)
