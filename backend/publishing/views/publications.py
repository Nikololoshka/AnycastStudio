from common.access import require_auth, require_get, require_post
from common.rate_limit import rate_limit
from common.request_body import validate
from common.responses import api_response, domain_errors
from config.wiring import container
from platforms.core.errors import NotFound
from platforms.core.publishing.request import NewPublication, NewTarget

from ..models import Publication
from .schemas import CreatePublicationSchema
from .serializers import publication_json


def _publications_of(user):
    return Publication.objects.filter(user=user).prefetch_related("targets").select_related("asset")


def _publication_json(user, publication_id: int) -> dict:
    return publication_json(_publications_of(user).get(pk=publication_id))


def _new_publication(request, data: CreatePublicationSchema) -> NewPublication:
    return NewPublication(
        owner_id=request.user.pk,
        asset_id=data.mediaAssetId,
        title=data.title,
        description=data.description,
        hashtags=tuple(data.hashtags),
        publish_at=data.publishAt,
        targets=tuple(NewTarget(target.platform, target.socialAccountId, target.settings) for target in data.targets),
    )


def _owned_target(request, pk: int) -> int:
    container().targets.ensure_owned(request.user.pk, pk)
    return pk


def _publication_of_target(request, target_id: int) -> dict:
    publication_id = Publication.objects.values_list("pk", flat=True).get(targets__pk=target_id)
    return _publication_json(request.user, publication_id)


@require_post
@require_auth
@rate_limit("publications")
@validate(CreatePublicationSchema)
@domain_errors
def publishing_create(request, data: CreatePublicationSchema):
    publication_id = container().publications.create(_new_publication(request, data))
    return api_response("ok", publication=_publication_json(request.user, publication_id))


@require_get
@require_auth
def publishing_publications(request):
    rows = _publications_of(request.user).order_by("-created_at")[:100]
    return api_response("ok", publications=[publication_json(row) for row in rows])


@require_get
@require_auth
@domain_errors
def publishing_publication(request, pk: int):
    row = _publications_of(request.user).filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return api_response("ok", publication=publication_json(row))


@require_post
@require_auth
@domain_errors
def publishing_cancel_target(request, pk: int):
    target_id = _owned_target(request, pk)
    container().publications.cancel(target_id)
    return api_response("ok", publication=_publication_of_target(request, target_id))


@require_post
@require_auth
@domain_errors
def publishing_retry_target(request, pk: int):
    target_id = _owned_target(request, pk)
    container().publications.retry(target_id)
    return api_response("ok", publication=_publication_of_target(request, target_id))
