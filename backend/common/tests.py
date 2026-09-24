import json

from django.core.cache import cache
from django.test import Client, TestCase

from .responses import api_response

LOGIN_URL = "/api/auth/login"


class ContractTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def post_login(self, body: bytes, client=None):
        return (client or self.client).post(LOGIN_URL, data=body, content_type="application/json")

    def body(self, response) -> dict:
        return json.loads(response.content)


class MalformedBodyScenarios(ContractTestCase):
    def test_a_body_that_is_not_utf8_is_invalid(self):
        # Given: bytes that no JSON decoder accepts as text
        # When: they are posted to an endpoint that validates its body
        response = self.post_login(b"\xff\xfe\x00")

        # Then: the client gets the invalid shape, not a 500
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["status"], "invalid")

    def test_a_body_nested_beyond_the_parser_is_invalid(self):
        # Given: JSON nested deeper than the parser's recursion limit
        # When: it is posted
        response = self.post_login(b"[" * 100_000)

        # Then: it is refused as invalid
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["status"], "invalid")


class CsrfScenarios(ContractTestCase):
    def test_a_post_without_a_csrf_token_answers_in_the_contract(self):
        # Given: a client that enforces CSRF and never fetched a token
        client = Client(enforce_csrf_checks=True)

        # When: it posts
        response = self.post_login(b"{}", client=client)

        # Then: the refusal carries a status string the SPA can branch on
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.body(response), {"status": "forbidden"})


class StatusScenarios(TestCase):
    def test_ok_answers_200(self):
        self.assertEqual(api_response("ok").status_code, 200)

    def test_an_unknown_status_is_refused(self):
        # Given / When: a status that is not in the contract
        # Then: it fails loudly instead of shipping as a success
        with self.assertRaises(KeyError):
            api_response("not_foud")
