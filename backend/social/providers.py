from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse


class ExchangeError(Exception):
    """Token exchange failed. `message` is safe to return to the client."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Provider:
    name: str
    error_code: str

    @property
    def redirect_uri(self) -> str:
        return f"https://{settings.PUBLIC_HOST}{reverse(f'{self.name}-callback')}"

    def build_auth_url(self, state: str) -> str:
        raise NotImplementedError

    def exchange_code(self, code: str) -> dict:
        """Return {"access_token", "token_type", "expires_in"} or raise ExchangeError."""
        raise NotImplementedError


def json_dict(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


class FacebookProvider(Provider):
    name = "facebook"
    error_code = "facebook_error"

    def build_auth_url(self, state: str) -> str:
        params = {
            "client_id": settings.FB_APP_ID,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": settings.FB_SCOPE,
        }
        return f"https://www.facebook.com/{settings.FB_GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        params = {
            "client_id": settings.FB_APP_ID,
            "redirect_uri": self.redirect_uri,
            "client_secret": settings.FB_APP_SECRET,
            "code": code,
        }
        try:
            response = requests.get(
                f"https://graph.facebook.com/{settings.FB_GRAPH_VERSION}/oauth/access_token",
                params=params,
                timeout=settings.HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            # The exception text may contain the request URL with the app secret.
            raise ExchangeError(f"Facebook request failed: {type(exc).__name__}") from None

        data = json_dict(response)
        if response.status_code != 200 or not data.get("access_token"):
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            message = error.get("message") or f"Unexpected response from Facebook (HTTP {response.status_code})"
            raise ExchangeError(str(message)[:500])

        return {
            "access_token": data["access_token"],
            "token_type": data.get("token_type", "bearer"),
            "expires_in": data.get("expires_in"),
        }


PROVIDERS: dict[str, Provider] = {p.name: p for p in (FacebookProvider(),)}
