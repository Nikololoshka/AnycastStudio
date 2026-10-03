from common.access import require_auth, require_get
from common.rate_limit import rate_limit
from common.responses import api_response, domain_errors
from config.wiring import container
from platforms2.core import PlatformType


@require_get
@require_auth
@rate_limit("creator_info")
@domain_errors
def social_creator_info(request, pk: int):
    owner_id = request.user.pk
    return api_response("ok", creatorInfo=container().run(lambda services: _creator_info(services, owner_id, pk)))


async def _creator_info(services, owner_id: int, account_id: int) -> dict:
    account = await container().accounts.owned_account(owner_id, account_id, PlatformType.TIKTOK)
    return await services.creator_info.info(account)
