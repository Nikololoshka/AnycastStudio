"""Sign-in for the SPA.

The session cookie is the credential: HttpOnly, so script cannot read it, and
same-origin, so CSRF protection applies normally. There is no registration and
no password reset here — accounts are created in the admin.
"""

from django.contrib.auth import authenticate
from django.contrib.auth import login as start_session
from django.contrib.auth import logout as end_session
from django.middleware.csrf import get_token

from common.guards import rate_limit, require_auth, require_get, require_post
from common.responses import api_response
from common.schema import validate

from ..schemas import LoginSchema
from ..serializers import user_json


@require_get
def csrf(request):
    """Seed the CSRF cookie. The SPA calls this once before its first mutation."""
    return api_response("ok", csrfToken=get_token(request))


@require_post
@rate_limit("login")
@validate(LoginSchema)
def login(request, data):
    user = authenticate(request, username=data.email, password=data.password)
    if user is None:
        # One message for a wrong address and a wrong password alike, so the
        # response does not reveal which addresses exist.
        return api_response("unauthorized", message="Incorrect email or password")

    start_session(request, user)
    return api_response("ok", user=user_json(user))


@require_post
@require_auth
def logout(request):
    end_session(request)
    return api_response("ok")


@require_get
@require_auth
def me(request):
    return api_response("ok", user=user_json(request.user))
