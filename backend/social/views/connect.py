from common.access import require_auth, require_post
from common.rate_limit import rate_limit
from common.responses import api_response, domain_errors
from config.wiring import container


@require_post
@require_auth
@rate_limit("connect")
@domain_errors
def social_connect(request, platform: str):
    return api_response("ok", authUrl=container().connect_flow.start(request.user.pk, platform))
