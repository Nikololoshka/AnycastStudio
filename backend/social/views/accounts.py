"""Listing and removing connected accounts."""

from common.access import require_auth, require_delete, require_get
from common.responses import api_response

from .. import services
from ..models import SocialAccount
from ..providers import PROVIDERS
from ..serializers import account_json


@require_get
@require_auth
def accounts(request):
    rows = SocialAccount.objects.filter(user=request.user).order_by("platform", "display_name")
    return api_response(
        "ok",
        accounts=[account_json(account) for account in rows],
        platforms=sorted(PROVIDERS),
    )


@require_delete
@require_auth
def account(request, pk: int):
    # Filtered by user, so another tenant's account is not found rather than forbidden.
    row = SocialAccount.objects.filter(user=request.user, pk=pk).first()
    if row is None:
        return api_response("not_found")

    services.disconnect(row)
    return api_response("ok")
