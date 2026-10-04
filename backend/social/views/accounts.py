from common.access import require_auth, require_delete, require_get
from common.responses import api_response, domain_errors
from platforms.core import PlatformType
from services.wiring import container

from ..models import SocialAccount
from .serializers import account_json


@require_get
@require_auth
def social_list_connected_accounts(request):
    accounts = (
        SocialAccount.objects.filter(user=request.user)
        .exclude(status=SocialAccount.Status.REVOKED)
        .order_by("platform", "display_name")
    )
    return api_response(
        status="ok",
        accounts=[account_json(account) for account in accounts],
        platforms=sorted(platform.value for platform in PlatformType),
    )


@require_delete
@require_auth
@domain_errors
def social_disconnect_account(request, pk: int):
    owner_id = request.user.pk
    container().run(lambda services: services.account_service.disconnect(owner_id, pk))
    return api_response("ok")
