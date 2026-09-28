from common.access import require_auth, require_get
from common.rate_limit import rate_limit
from common.responses import api_response, domain_errors
from config.wiring import container


@require_get
@require_auth
@rate_limit("creator_info")
@domain_errors
def social_creator_info(request, pk: int):
    account = container().accounts.owned_account(request.user.pk, pk, "tiktok")
    return api_response("ok", creatorInfo=container().creator_info.info(account))
