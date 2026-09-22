"""Listing and removing uploaded files."""

from common.guards import require_auth, require_delete, require_get
from common.responses import api_response

from .. import services
from ..models import MediaAsset
from ..serializers import asset_json


@require_get
@require_auth
def assets(request):
    rows = MediaAsset.objects.filter(user=request.user, status=MediaAsset.Status.READY).order_by(
        "-created_at"
    )
    return api_response(
        "ok",
        assets=[asset_json(asset) for asset in rows],
        usedBytes=services.stored_bytes(request.user),
        quotaBytes=request.user.quota.max_storage_bytes,
    )


@require_delete
@require_auth
def asset(request, pk: int):
    row = MediaAsset.objects.filter(user=request.user, pk=pk, status=MediaAsset.Status.READY).first()
    if row is None:
        return api_response("not_found")

    services.delete_asset(row)
    return api_response("ok")
