from urllib.parse import parse_qs, urlparse

from django.test import override_settings

from social.models import OAuthSession
from social.tests.base import CALLBACK_URL, CODE, CONNECT_URL, SocialTestCase

TUNNEL_ORIGIN = "https://anycast.ngrok-free.app"
TUNNEL_HOST = "anycast.ngrok-free.app"


@override_settings(PUBLIC_REDIRECT_ORIGIN=TUNNEL_ORIGIN, ALLOWED_HOSTS=["testserver", TUNNEL_HOST])
class RedirectOriginScenarios(SocialTestCase):
    def test_the_platform_is_told_to_redirect_to_the_redirect_origin(self):
        # Given: the platform only accepts an HTTPS redirect, served by a tunnel
        self.sign_in()

        # When: a connection is started from the app
        query = parse_qs(urlparse(self.body(self.client.post(CONNECT_URL))["authUrl"]).query)

        # Then: the redirect goes through the tunnel
        self.assertEqual(query["redirect_uri"], [f"{TUNNEL_ORIGIN}/api/social/youtube/callback"])

    def test_a_callback_arriving_through_the_tunnel_is_sent_on_to_the_app(self):
        # Given: a started connection, and the platform sending the browser to the tunnel
        self.sign_in()
        state = self.given_started_connection()

        # When: the callback arrives on the tunnel's host, without the app's cookie
        self.client.logout()
        response = self.client.get(CALLBACK_URL, {"state": state, "code": CODE}, HTTP_HOST=TUNNEL_HOST)

        # Then: the browser is sent to the app's origin with the same query, and nothing was exchanged
        location = urlparse(response["Location"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(f"{location.scheme}://{location.netloc}", "http://testserver")
        self.assertEqual(location.path, CALLBACK_URL)
        self.assertEqual(parse_qs(location.query), {"state": [state], "code": [CODE]})
        self.assertEqual(self.http.sent, [])
        self.assertEqual(OAuthSession.objects.get().status, OAuthSession.Status.PENDING)

    def test_the_forwarded_callback_connects_the_account_with_the_same_redirect_uri(self):
        # Given: the callback was forwarded to the app's origin
        self.sign_in()
        state = self.given_started_connection()

        # When: it arrives with the app's cookie
        response = self.callback(state=state, code=CODE)

        # Then: the account is connected, and the exchange named the redirect the platform saw
        self.assertIn("result=connected", response["Location"])
        exchange = self.http.sent[0].data
        self.assertEqual(exchange["redirect_uri"], f"{TUNNEL_ORIGIN}/api/social/youtube/callback")
