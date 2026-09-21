from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .. import sessions
from ..providers import PROVIDERS
from .common import api_response, rate_limit, require_client_token, require_post


@csrf_exempt
@require_post
@rate_limit("start")
@require_client_token
def start(request, provider):
    provider = PROVIDERS[provider]
    state, poll_token = sessions.create(provider.name)
    return api_response(
        "ok",
        auth_url=provider.build_auth_url(state),
        poll_token=poll_token,
        expires_in=settings.AUTH_SESSION_TTL,
    )
