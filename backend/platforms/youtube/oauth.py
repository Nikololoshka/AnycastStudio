"""Connecting a YouTube channel.

Google is a standard OAuth 2.0 provider with PKCE. Two details decide whether
the connection survives:

- access_type=offline together with prompt=consent is what makes Google issue a
  refresh token at all, and re-issue one if the person reconnects;
- Google does not return the refresh token when refreshing, so the stored one
  must be carried forward. TokenBundle.merged_with does that.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from ..base import Identity, ProviderError, TokenBundle
from ..http import json_dict, request

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"


class YouTubeProvider:
    name = "youtube"
    label = "YouTube"
    uses_pkce = True
    scopes = (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    )

    @property
    def redirect_uri(self) -> str:
        return f"{settings.PUBLIC_ORIGIN}{reverse('social-callback', args=[self.name])}"

    def _client_id(self) -> str:
        if not settings.YOUTUBE_CLIENT_ID:
            raise ProviderError("YOUTUBE_CLIENT_ID is not configured")
        return settings.YOUTUBE_CLIENT_ID

    def _client_secret(self) -> str:
        if not settings.YOUTUBE_CLIENT_SECRET:
            raise ProviderError("YOUTUBE_CLIENT_SECRET is not configured")
        return settings.YOUTUBE_CLIENT_SECRET

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_id": self._client_id(),
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    def _post_token(self, data: dict) -> TokenBundle:
        response = request("POST", TOKEN_ENDPOINT, label="Google", data=data)
        body = json_dict(response)

        if response.status_code != 200 or not body.get("access_token"):
            message = body.get("error_description") or body.get("error")
            raise ProviderError(
                str(message or f"Unexpected response from Google (HTTP {response.status_code})")[:500]
            )

        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            scopes=tuple(str(body.get("scope", "")).split()) or self.scopes,
        )

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        return self._post_token(
            {
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "code": code,
                "code_verifier": code_verifier or "",
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenBundle:
        return self._post_token(
            {
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )

    def fetch_identity(self, access_token: str) -> Identity:
        response = request(
            "GET",
            CHANNELS_ENDPOINT,
            label="Google",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        body = json_dict(response)

        if response.status_code != 200:
            message = (body.get("error") or {}).get("message")
            raise ProviderError(str(message or "Could not read the YouTube channel")[:500])

        items = body.get("items") or []
        if not items:
            raise ProviderError("This Google account has no YouTube channel")

        channel = items[0]
        snippet = channel.get("snippet") or {}
        thumbnails = snippet.get("thumbnails") or {}

        return Identity(
            external_id=str(channel.get("id", "")),
            display_name=snippet.get("title", ""),
            avatar_url=(thumbnails.get("default") or {}).get("url", ""),
            extra={"customUrl": snippet.get("customUrl", "")},
        )

    def revoke(self, token: str) -> None:
        # Best effort: the account is disconnected here regardless of what Google says.
        request("POST", REVOKE_ENDPOINT, label="Google", data={"token": token})
