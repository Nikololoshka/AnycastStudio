from common.access import require_auth, require_get
from common.rate_limit import rate_limit
from common.responses import api_response, domain_errors
from services.wiring import container


@require_get
@require_auth
@rate_limit("creator_info")
@domain_errors
def social_get_tiktok_creator_info(request, pk: int):
    owner_id = request.user.pk
    creator_info = container().run(lambda services: services.creator_info.info(owner_id, pk))
    return api_response("ok", creatorInfo=creator_info)
