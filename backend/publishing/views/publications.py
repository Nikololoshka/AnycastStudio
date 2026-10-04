from common.access import require_auth, require_get, require_post
from common.rate_limit import rate_limit
from common.request_body import validate
from common.responses import api_response, domain_errors
from services.core.domain import NotFound
from services.wiring import container

from ..models import Publication
from .schemas import CreatePublicationSchema
from .serializers import publication_json


def _owned_publications(user):
    return Publication.objects.filter(user=user).prefetch_related("targets").select_related("asset")


@require_post
@require_auth
@rate_limit("publications")
@validate(CreatePublicationSchema)
@domain_errors
def publishing_create_publication(request, data: CreatePublicationSchema):
    publication = data.as_new_publication(request.user.pk)
    publication_id = container().run(lambda services: services.publications.create(publication))
    return api_response("ok", publication=publication_json(_owned_publications(request.user).get(pk=publication_id)))


@require_get
@require_auth
def publishing_list_publications(request):
    publications = _owned_publications(request.user).order_by("-created_at")[:100]
    return api_response("ok", publications=[publication_json(publication) for publication in publications])


@require_get
@require_auth
@domain_errors
def publishing_get_publication(request, pk: int):
    publication = _owned_publications(request.user).filter(pk=pk).first()
    if publication is None:
        raise NotFound()
    return api_response("ok", publication=publication_json(publication))


@require_post
@require_auth
@domain_errors
def publishing_cancel_target(request, pk: int):
    owner_id = request.user.pk
    container().run(lambda services: services.publications.cancel(owner_id, pk))
    return api_response("ok", publication=publication_json(_owned_publications(request.user).get(targets__pk=pk)))


@require_post
@require_auth
@domain_errors
def publishing_retry_target(request, pk: int):
    owner_id = request.user.pk
    container().run(lambda services: services.publications.retry(owner_id, pk))
    return api_response("ok", publication=publication_json(_owned_publications(request.user).get(targets__pk=pk)))
