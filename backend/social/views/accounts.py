from common.access import require_auth, require_delete, require_get
from common.responses import api_response

from .. import services
from ..models import SocialAccount
from ..providers import PROVIDERS
from .serializers import account_json


@require_get
@require_auth
def social_accounts(request):
    rows = _connected_accounts_of(request.user).order_by("platform", "display_name")
    return api_response(
        status="ok",
        accounts=[account_json(account) for account in rows],
        platforms=sorted(PROVIDERS),
    )


@require_delete
@require_auth
def social_account(request, pk: int):
    row = _connected_accounts_of(request.user).filter(pk=pk).first()
    if row is None:
        return api_response("not_found")

    services.disconnect(row)
    return api_response("ok")


def _connected_accounts_of(user):
    return SocialAccount.objects.filter(user=user).exclude(status=SocialAccount.Status.REVOKED)
