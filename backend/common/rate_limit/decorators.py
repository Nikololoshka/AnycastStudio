from ..core.decorators import precondition_with_params
from ..responses import api_response
from .counter import is_rate_limited


@precondition_with_params
def rate_limit(request, scope):
    if is_rate_limited(request, scope):
        return api_response("rate_limited")
