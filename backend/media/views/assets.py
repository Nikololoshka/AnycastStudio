from common.access import require_auth, require_delete, require_get
from common.responses import api_response

from .. import services
from ..models import MediaAsset
from .serializers import asset_json


def _ready_assets_of(user):
    return MediaAsset.objects.filter(user=user, status=MediaAsset.Status.READY)


@require_get
@require_auth
def media_assets(request):
    rows = _ready_assets_of(request.user).order_by("-created_at")
    return api_response(
        "ok",
        assets=[asset_json(asset) for asset in rows],
        usedBytes=services.stored_bytes(request.user),
        quotaBytes=request.user.max_storage_bytes,
    )


@require_delete
@require_auth
def media_asset(request, pk: int):
    row = _ready_assets_of(request.user).filter(pk=pk).first()
    if row is None:
        return api_response("not_found")
    if services.is_in_use(row):
        return api_response("conflict", message="asset_in_use")

    services.delete_asset(row)
    return api_response("ok")
