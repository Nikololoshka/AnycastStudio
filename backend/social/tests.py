"""Scenarios for the Facebook OAuth broker, written as Given / When / Then.

The Graph API is mocked: no test touches the network.
"""

import asyncio
import logging
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

import requests
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import AuthSession, hash_token

START_URL = "/api/social/auth_facebook/start"
CALLBACK_URL = "/api/social/auth_facebook/callback"
POLL_URL = "/api/social/auth_facebook/poll"
REDIRECT_URI = "https://auth.test/api/social/auth_facebook/callback"
SECRET = "test-app-secret-DO-NOT-LEAK"
ACCESS_TOKEN = "EAAB-fake-access-token-123"
CODE = "the-code"
CLIENT_TOKEN = "test-client-token"  # see config/settings/test.py
CLIENT_AUTH = {"Authorization": f"Bearer {CLIENT_TOKEN}"}


def graph_response(status=200, payload=None):
    """A fake `requests` response from the Graph API token endpoint; payload=None means non-JSON body."""
    response = mock.Mock()
    response.status_code = status
    if payload is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = payload
    return response


def graph_ok():
    return graph_response(200, {"access_token": ACCESS_TOKEN, "token_type": "bearer", "expires_in": 5183944})


class BrokerTestCase(TestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters
        patcher = mock.patch("social.providers.requests.get")
        self.graph_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.graph_get.return_value = graph_ok()

    # --- steps ---

    def given_started_login(self):
        """Desktop called /start. Returns (response body, state from auth_url)."""
        response = self.client.post(START_URL, headers=CLIENT_AUTH)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        state = parse_qs(urlparse(data["auth_url"]).query)["state"][0]
        return data, state

    def given_graph_api_returns(self, response_or_exception):
        if isinstance(response_or_exception, Exception):
            self.graph_get.side_effect = response_or_exception
        else:
            self.graph_get.return_value = response_or_exception

    def given_sessions_expired(self):
        AuthSession.objects.update(created_at=timezone.now() - timedelta(seconds=601))

    def callback(self, **params):
        return self.client.get(CALLBACK_URL, params)

    def poll(self, token):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return self.client.post(POLL_URL, headers=headers)


class StartScenarios(BrokerTestCase):
    def test_start_returns_facebook_login_link(self):
        # Given: a configured Facebook app (see settings_test)

        # When: the desktop starts a login
        data, state = self.given_started_login()

        # Then: it gets a Facebook dialog link with the app's parameters
        parsed = urlparse(data["auth_url"])
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ("https", "www.facebook.com", "/v23.0/dialog/oauth"))
        query = parse_qs(parsed.query)
        self.assertEqual(query["client_id"], ["test-app-id"])
        self.assertEqual(query["redirect_uri"], [REDIRECT_URI])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], [settings.FB_SCOPE])
        self.assertEqual(query["state"], [state])
        # And: the session TTL
        self.assertEqual(data["expires_in"], 600)

    def test_start_stores_only_poll_token_hash(self):
        # Given: nothing

        # When: the desktop starts a login
        data, state = self.given_started_login()

        # Then: a pending session exists and stores the hash of poll_token, not the token itself
        session = AuthSession.objects.get()
        self.assertEqual(session.state, state)
        self.assertEqual(session.status, AuthSession.Status.PENDING)
        self.assertEqual(session.poll_token_hash, hash_token(data["poll_token"]))
        self.assertNotIn(data["poll_token"], AuthSession.objects.values().get().values())
        # And: state and poll_token are different values
        self.assertNotEqual(data["poll_token"], state)

    def test_start_deletes_expired_sessions(self):
        # Given: an old session that has outlived its TTL
        self.given_started_login()
        self.given_sessions_expired()

        # When: a new login is started
        _, fresh_state = self.given_started_login()

        # Then: only the new session remains
        self.assertEqual(list(AuthSession.objects.values_list("state", flat=True)), [fresh_state])

    @override_settings(RATE_LIMITS={"start": (2, 60), "poll": (100, 60)})
    def test_start_is_rate_limited(self):
        # Given: a client that already used its limit of 2 starts
        self.given_started_login()
        self.given_started_login()

        # When: it starts once more
        response = self.client.post(START_URL, headers=CLIENT_AUTH)

        # Then: the request is rejected
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"status": "rate_limited"})

    def assert_start_unauthorized(self, headers):
        """Then: /start answers 401 unauthorized and creates no session."""
        response = self.client.post(START_URL, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"status": "unauthorized"})
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
        self.assertFalse(AuthSession.objects.exists())

    def test_start_without_client_token(self):
        # When: a client starts a login without a token
        # Then: it is rejected
        self.assert_start_unauthorized({})

    def test_start_with_wrong_client_token(self):
        # When: a client starts a login with a token the server does not know, or another scheme
        # Then: both are rejected
        self.assert_start_unauthorized({"Authorization": "Bearer wrong-token"})
        self.assert_start_unauthorized({"Authorization": f"Basic {CLIENT_TOKEN}"})

    def test_client_token_in_url_is_ignored(self):
        # When: the client token is sent in the query string instead of the header
        response = self.client.post(f"{START_URL}?client_token={CLIENT_TOKEN}")

        # Then: it is not accepted
        self.assertEqual(response.status_code, 401)

    @override_settings(CLIENT_TOKENS=["old-token", "new-token"])
    def test_any_configured_client_token_is_accepted(self):
        # Given: two tokens configured while the desktop app moves to the new one
        for token in ("old-token", "new-token"):
            # When: a client starts a login with either of them
            response = self.client.post(START_URL, headers={"Authorization": f"Bearer {token}"})

            # Then: it gets a login link
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")

    @override_settings(CLIENT_TOKENS=[])
    def test_no_configured_client_tokens_rejects_everyone(self):
        # Given: no client tokens configured
        # When: a client starts a login with any token
        # Then: it is rejected
        self.assert_start_unauthorized(CLIENT_AUTH)

    def test_client_token_is_not_a_poll_token(self):
        # Given: a started login
        self.given_started_login()

        # When: someone polls with the client token
        response = self.poll(CLIENT_TOKEN)

        # Then: it does not grant access
        self.assertEqual(response.status_code, 404)

    def test_start_rejects_get(self):
        # When: /start is called with GET
        response = self.client.get(START_URL)

        # Then: method not allowed, as JSON
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json(), {"status": "method_not_allowed"})
        self.assertEqual(response["Allow"], "POST")

    def test_unknown_provider_has_no_endpoint(self):
        # When: a start is requested for a system that is not configured
        response = self.client.post("/api/social/auth_myspace/start", headers=CLIENT_AUTH)

        # Then: not found, as JSON
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"status": "not_found"})


class CallbackScenarios(BrokerTestCase):
    def test_successful_login_delivers_token_once(self):
        # Given: a started login
        data, state = self.given_started_login()

        # When: Facebook redirects back with a code
        response = self.callback(state=state, code=CODE)

        # Then: the browser sees the success page
        self.assertEqual(response.status_code, 200)
        # And: the code was exchanged with the app secret and the same redirect_uri
        self.graph_get.assert_called_once()
        args, kwargs = self.graph_get.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v23.0/oauth/access_token")
        self.assertEqual(
            kwargs["params"],
            {"client_id": "test-app-id", "redirect_uri": REDIRECT_URI, "client_secret": SECRET, "code": CODE},
        )

        # When: the desktop polls
        response = self.poll(data["poll_token"])

        # Then: it receives the token
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "done",
                "provider": "facebook",
                "access_token": ACCESS_TOKEN,
                "token_type": "bearer",
                "expires_in": 5183944,
            },
        )

        # When: the desktop polls again
        response = self.poll(data["poll_token"])

        # Then: the result is gone
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AuthSession.objects.exists())

    def test_user_cancels_login(self):
        # Given: a started login
        data, state = self.given_started_login()

        # When: the user declines and Facebook redirects back with an error
        response = self.callback(
            state=state, error="access_denied", error_reason="user_denied", error_description="Permissions error"
        )

        # Then: the browser sees the "cancelled" page and no code exchange happens
        self.assertEqual(response.status_code, 200)
        self.graph_get.assert_not_called()
        # And: the desktop receives the error
        response = self.poll(data["poll_token"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "error", "error": "access_denied", "error_reason": "user_denied"})

    def assert_exchange_failed(self, data, response):
        """Then: the browser gets 502 and the desktop gets facebook_error without a token."""
        self.assertEqual(response.status_code, 502)
        body = self.poll(data["poll_token"]).json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"], "facebook_error")
        self.assertIn("message", body)
        self.assertNotIn("access_token", body)
        return body

    def test_code_exchange_rejected_by_facebook(self):
        # Given: Facebook rejects the code
        self.given_graph_api_returns(
            graph_response(400, {"error": {"message": "Invalid verification code format.", "code": 100}})
        )
        data, state = self.given_started_login()

        # When: the callback arrives
        response = self.callback(state=state, code="bad-code")

        # Then: the exchange fails with Facebook's message
        body = self.assert_exchange_failed(data, response)
        self.assertEqual(body["message"], "Invalid verification code format.")

    def test_code_exchange_returns_no_token(self):
        # Given: Facebook answers 200 but without access_token
        self.given_graph_api_returns(graph_response(200, {"something": "else"}))
        data, state = self.given_started_login()

        # When: the callback arrives
        response = self.callback(state=state, code="bad-code")

        # Then: the exchange fails
        self.assert_exchange_failed(data, response)

    def test_code_exchange_returns_non_json(self):
        # Given: Facebook answers 500 with a non-JSON body
        self.given_graph_api_returns(graph_response(500, None))
        data, state = self.given_started_login()

        # When: the callback arrives
        response = self.callback(state=state, code="bad-code")

        # Then: the exchange fails
        self.assert_exchange_failed(data, response)

    def test_code_exchange_network_error(self):
        # Given: Facebook is unreachable, and the exception text contains the secret
        self.given_graph_api_returns(requests.ConnectionError(f"https://graph.facebook.com/?client_secret={SECRET}"))
        data, state = self.given_started_login()

        # When: the callback arrives
        response = self.callback(state=state, code="bad-code")

        # Then: the exchange fails and the secret does not reach the desktop
        body = self.assert_exchange_failed(data, response)
        self.assertNotIn(SECRET, body["message"])

    def test_unknown_or_missing_state_is_rejected(self):
        # Given: a started login
        self.given_started_login()

        # When: callbacks arrive with a state the server never issued, or without state
        wrong_state = self.callback(state="nope", code="c")
        no_state = self.callback(code="c")

        # Then: both are rejected and Facebook is not called
        self.assertEqual(wrong_state.status_code, 400)
        self.assertEqual(no_state.status_code, 400)
        self.graph_get.assert_not_called()

    def test_repeated_state_is_rejected(self):
        # Given: a login whose callback was already processed
        _, state = self.given_started_login()
        self.assertEqual(self.callback(state=state, code="c").status_code, 200)
        self.graph_get.reset_mock()

        # When: the same callback arrives again
        response = self.callback(state=state, code="c")

        # Then: it is rejected and Facebook is not called
        self.assertEqual(response.status_code, 400)
        self.graph_get.assert_not_called()

    def test_expired_session_is_rejected(self):
        # Given: a login that has outlived its TTL
        data, state = self.given_started_login()
        self.given_sessions_expired()

        # When: the callback arrives
        response = self.callback(state=state, code="c")

        # Then: it is rejected without calling Facebook
        self.assertEqual(response.status_code, 400)
        self.graph_get.assert_not_called()
        # And: the desktop is told the session expired
        self.assertEqual(self.poll(data["poll_token"]).status_code, 410)

    def test_secrets_do_not_leak_to_logs_or_page(self):
        # Given: a started login
        data, state = self.given_started_login()

        # When: the login completes and the token is picked up, with all logging captured
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger("social").debug("marker")  # assertLogs fails if nothing is logged
            page = self.callback(state=state, code=CODE)
            poll_response = self.poll(data["poll_token"])

        # Then: the token was delivered to the desktop
        self.assertEqual(poll_response.json()["access_token"], ACCESS_TOKEN)
        # And: neither the page nor the logs contain the secret, token, code or poll token
        html = page.content.decode()
        output = "\n".join(logs.output)
        for secret in (SECRET, ACCESS_TOKEN, CODE, data["poll_token"]):
            self.assertNotIn(secret, html)
            self.assertNotIn(secret, output)

    def test_page_does_not_echo_request_parameters(self):
        # Given: a started login
        _, state = self.given_started_login()

        # When: the callback carries markup in its parameters
        response = self.callback(state=state, error="<script>x</script>", error_reason="<b>r</b>")

        # Then: the page does not include it
        html = response.content.decode()
        self.assertNotIn("<script>x", html)
        self.assertNotIn("<b>r</b>", html)


class PollScenarios(BrokerTestCase):
    def test_poll_without_authorization_header(self):
        # When: the desktop polls without a token
        response = self.poll(None)

        # Then: unauthorized
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"status": "unauthorized"})

    def test_poll_with_non_bearer_authorization(self):
        # When: the Authorization header uses another scheme
        response = self.client.post(POLL_URL, headers={"Authorization": "Basic abc"})

        # Then: unauthorized
        self.assertEqual(response.status_code, 401)

    def test_poll_with_wrong_token(self):
        # Given: a started login
        self.given_started_login()

        # When: the desktop polls with a token the server never issued
        response = self.poll("wrong-token")

        # Then: not found
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"status": "not_found"})

    def test_poll_token_in_url_is_ignored(self):
        # Given: a started login
        data, _ = self.given_started_login()

        # When: the poll token is sent in the query string instead of the header
        response = self.client.post(f"{POLL_URL}?poll_token={data['poll_token']}")

        # Then: it is not accepted
        self.assertEqual(response.status_code, 401)

    def test_state_is_not_a_poll_token(self):
        # Given: a started login whose state is public (it went to Facebook)
        _, state = self.given_started_login()

        # When: someone polls with the state
        response = self.poll(state)

        # Then: it does not grant access
        self.assertEqual(response.status_code, 404)

    def test_poll_returns_pending_on_timeout(self):
        # Given: a started login with no callback yet
        data, _ = self.given_started_login()

        # When: the desktop polls and the wait times out (0.3 s in settings_test)
        response = self.poll(data["poll_token"])

        # Then: it is told to retry, and the session stays
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "pending"})
        self.assertTrue(AuthSession.objects.exists())

    def test_poll_rejects_get(self):
        # When: /poll is called with GET
        response = self.client.get(POLL_URL)

        # Then: method not allowed, as JSON
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json(), {"status": "method_not_allowed"})

    async def test_poll_returns_token_when_callback_arrives_during_wait(self):
        # Given: a started login and a poll that is already waiting
        data, state = await sync_to_async(self.given_started_login)()
        waiting_poll = asyncio.create_task(
            self.async_client.post(POLL_URL, headers={"Authorization": f"Bearer {data['poll_token']}"})
        )
        await asyncio.sleep(0.1)
        self.assertFalse(waiting_poll.done())

        # When: the callback arrives while the poll waits
        callback = await sync_to_async(self.callback)(state=state, code=CODE)
        self.assertEqual(callback.status_code, 200)

        # Then: the waiting poll returns the token
        response = await waiting_poll
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "done")
        self.assertEqual(response.json()["access_token"], ACCESS_TOKEN)
