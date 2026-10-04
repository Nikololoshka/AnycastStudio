from common.access import require_auth, require_delete, require_get
from common.responses import api_response, domain_errors
from platforms.core import PlatformType
from services.wiring import container

from ..models import SocialAccount
from .serializers import account_json


@require_get
@require_auth
def social_accounts(request):
    rows = _connected_accounts_of(request.user).order_by("platform", "display_name")
    return api_response(
        status="ok",
        accounts=[account_json(account) for account in rows],
        platforms=sorted(platform.value for platform in PlatformType),
    )


@require_delete
@require_auth
@domain_errors
def social_account(request, pk: int):
    owner_id = request.user.pk
    container().run(lambda services: _disconnect(services, owner_id, pk))
    return api_response("ok")


async def _disconnect(services, owner_id: int, account_id: int) -> None:
    account = await container().accounts.owned_account(owner_id, account_id)
    await services.account_service.disconnect(account.id)


def _connected_accounts_of(user):
    return SocialAccount.objects.filter(user=user).exclude(status=SocialAccount.Status.REVOKED)
