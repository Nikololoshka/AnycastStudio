from common.access import require_auth, require_delete, require_get, require_post
from common.request_body import validate
from common.responses import api_response
from media.models import MediaAsset

from ..models import Draft
from .schemas import DraftSchema
from .serializers import draft_json


def _owned_drafts(user):
    return Draft.objects.filter(user=user).select_related("asset")


def _unknown_asset(request, data: DraftSchema):
    if data.mediaAssetId is None:
        return None
    if MediaAsset.objects.filter(user=request.user, pk=data.mediaAssetId, status=MediaAsset.Status.READY).exists():
        return None
    return api_response("invalid", errors=[{"field": "mediaAssetId", "message": "no such media asset"}])


@require_get
@require_auth
def publishing_list_drafts(request):
    drafts = _owned_drafts(request.user).order_by("-updated_at")
    return api_response("ok", drafts=[draft_json(draft) for draft in drafts])


@require_post
@require_auth
@validate(DraftSchema)
def publishing_create_draft(request, data: DraftSchema):
    if refusal := _unknown_asset(request, data):
        return refusal

    draft = Draft.objects.create(user=request.user, **data.as_fields())
    return api_response("ok", draft=draft_json(_owned_drafts(request.user).get(pk=draft.pk)))


@require_get
@require_auth
def publishing_get_draft(request, pk: int):
    draft = _owned_drafts(request.user).filter(pk=pk).first()
    if draft is None:
        return api_response("not_found")
    return api_response("ok", draft=draft_json(draft))


@require_post
@require_auth
@validate(DraftSchema)
def publishing_update_draft(request, data: DraftSchema, pk: int):
    draft = _owned_drafts(request.user).filter(pk=pk).first()
    if draft is None:
        return api_response("not_found")
    if refusal := _unknown_asset(request, data):
        return refusal

    for field, value in data.as_fields().items():
        setattr(draft, field, value)
    draft.save()
    return api_response("ok", draft=draft_json(_owned_drafts(request.user).get(pk=pk)))


@require_delete
@require_auth
def publishing_delete_draft(request, pk: int):
    deleted, _ = _owned_drafts(request.user).filter(pk=pk).delete()
    if not deleted:
        return api_response("not_found")
    return api_response("ok")
