from ..guard import guard
from ..responses import api_response


def require_method(method: str):
    @guard
    def decorator(request, *args, **kwargs):
        if request.method != method:
            return api_response("method_not_allowed", headers={"Allow": method})

    return decorator


require_post = require_method("POST")
require_get = require_method("GET")
require_delete = require_method("DELETE")


@guard
def require_auth(request, *args, **kwargs):
    if not request.user.is_authenticated:
        return api_response("unauthorized")
