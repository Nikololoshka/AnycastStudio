"""Start connecting a platform account.

The browser is redirected to the platform and comes back to our callback, so
no polling is needed: the person is signed in the whole time.
"""

import logging

from common.guards import rate_limit, require_auth, require_post
from common.responses import api_response
from platforms.base import ProviderError

from .. import sessions
from ..providers import get_provider

logger = logging.getLogger(__name__)


@require_post
@require_auth
@rate_limit("connect")
def connect(request, platform: str):
    provider = get_provider(platform)
    if provider is None:
        return api_response("not_found")

    session, challenge = sessions.create(request.user, provider.name, provider.uses_pkce)

    try:
        auth_url = provider.authorize_url(session.state, challenge)
    except ProviderError as error:
        # The platform's credentials are missing from the environment. Say so
        # plainly rather than answering with a 500 the person cannot act on.
        sessions.finish(session, sessions.Status.ERROR)
        logger.error("Cannot start %s sign-in: %s", provider.name, error.message)
        return api_response("server_error", message=error.message)

    return api_response("ok", authUrl=auth_url)
