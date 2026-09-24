import json

from django.core.cache import cache
from django.test import TestCase

LOGIN_URL = "/api/auth/login"


class MalformedBodyScenarios(TestCase):
    def setUp(self):
        cache.clear()

    def post_login(self, body: bytes):
        return self.client.post(LOGIN_URL, data=body, content_type="application/json")

    def assert_invalid(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["status"], "invalid")

    def test_a_body_that_is_not_utf8_is_invalid(self):
        # Given: bytes that no JSON decoder accepts as text
        # When: they are posted to an endpoint that validates its body
        response = self.post_login(b"\xff\xfe\x00")

        # Then: the client gets the invalid shape, not a 500
        self.assert_invalid(response)

    def test_a_body_nested_beyond_the_parser_is_invalid(self):
        # Given: JSON nested deeper than the parser's recursion limit
        # When: it is posted
        response = self.post_login(b"[" * 100_000)

        # Then: it is refused as invalid
        self.assert_invalid(response)
