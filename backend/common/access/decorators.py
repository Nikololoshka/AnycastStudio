from ..core.decorators import precondition, precondition_with_params
from ..responses import api_response


@precondition
def require_auth(request):
    if not request.user.is_authenticated:
        return api_response("unauthorized")


@precondition_with_params
def require_method(request, method):
    if request.method != method:
        return api_response("method_not_allowed", headers={"Allow": method})


require_post = require_method("POST")
require_get = require_method("GET")
require_patch = require_method("PATCH")
require_delete = require_method("DELETE")
