from django.contrib.auth import authenticate
from django.contrib.auth import login as start_session
from django.contrib.auth import logout as end_session
from django.middleware.csrf import get_token

from common.access import require_auth, require_get, require_patch, require_post
from common.rate_limit import rate_limit
from common.request_body import validate
from common.responses import api_response

from .schemas import LoginSchema, PreferencesSchema
from .serializers import user_json


@require_get
def account_csrf(request):
    return api_response("ok", csrfToken=get_token(request))


@require_post
@rate_limit("login")
@validate(LoginSchema)
def account_login(request, data: LoginSchema):
    user = authenticate(request, username=data.email, password=data.password)
    if user is None:
        return api_response("unauthorized", message="Incorrect email or password")

    start_session(request, user)
    return api_response("ok", user=user_json(user))


@require_post
@require_auth
def account_logout(request):
    end_session(request)
    return api_response("ok")


@require_get
@require_auth
def account_me(request):
    return api_response("ok", user=user_json(request.user))


@require_patch
@require_auth
@validate(PreferencesSchema)
def account_update_preferences(request, data: PreferencesSchema):
    fields = data.as_fields()
    for field, value in fields.items():
        setattr(request.user, field, value)
    request.user.save(update_fields=list(fields))
    return api_response("ok", user=user_json(request.user))
