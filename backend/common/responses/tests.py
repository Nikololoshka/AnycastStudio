import json

from django.core.cache import cache
from django.test import Client, TestCase

from .contract import api_response

LOGIN_URL = "/api/auth/login"


class CsrfScenarios(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_post_without_a_csrf_token_answers_in_the_contract(self):
        # Given: a client that enforces CSRF and never fetched a token
        client = Client(enforce_csrf_checks=True)

        # When: it posts
        response = client.post(LOGIN_URL, data=b"{}", content_type="application/json")

        # Then: the refusal carries a status string the SPA can branch on
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content), {"status": "forbidden"})


class StatusScenarios(TestCase):
    def test_ok_answers_200(self):
        self.assertEqual(api_response("ok").status_code, 200)

    def test_an_unknown_status_is_refused(self):
        # Given / When: a status that is not in the contract
        # Then: it fails loudly instead of shipping as a success
        with self.assertRaises(KeyError):
            api_response("not_foud")
