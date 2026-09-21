"""Authentication for the legacy desktop broker endpoints.

The desktop client shipped a shared token because it had no user session. The
browser flow replaces this: the person is already signed in when they connect
an account. Removed together with start/poll.
"""

import hmac

from django.conf import settings

from common.guards import bearer_token, guard
from common.responses import unauthorized_response


@guard
def require_client_token(request, *args, **kwargs):
    token = bearer_token(request)
    if token is None:
        return unauthorized_response()
    # Every token is compared, without short-circuiting, so timing does not reveal which one matched.
    matches = [hmac.compare_digest(token.encode(), known.encode()) for known in settings.CLIENT_TOKENS]
    if not any(matches):
        return unauthorized_response()
