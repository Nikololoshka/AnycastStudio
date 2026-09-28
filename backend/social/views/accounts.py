from common.access import require_auth, require_delete, require_get
from common.responses import api_response, domain_errors
from config.wiring import container

from ..models import SocialAccount
from .serializers import account_json


@require_get
@require_auth
def social_accounts(request):
    rows = _connected_accounts_of(request.user).order_by("platform", "display_name")
    return api_response(
        status="ok",
        accounts=[account_json(account) for account in rows],
        platforms=sorted(container().catalog.names()),
    )


@require_delete
@require_auth
@domain_errors
def social_account(request, pk: int):
    account = container().accounts.owned_account(request.user.pk, pk)
    container().account_service.disconnect(account.id)
    return api_response("ok")


def _connected_accounts_of(user):
    return SocialAccount.objects.filter(user=user).exclude(status=SocialAccount.Status.REVOKED)
