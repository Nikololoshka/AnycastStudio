import json

from .base import CSRF_URL, EMAIL, LOGIN_URL, PASSWORD, BaseAuthTestCase


class CsrfScenarios(BaseAuthTestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_class(enforce_csrf_checks=True)

    def test_post_without_the_header_is_rejected(self):
        self.given_a_user()

        response = self.login()

        self.assertEqual(response.status_code, 403)

    def test_post_with_the_header_is_accepted(self):
        self.given_a_user()
        token = self.body(self.client.get(CSRF_URL))["csrfToken"]

        response = self.client.post(
            LOGIN_URL,
            data=json.dumps({"email": EMAIL, "password": PASSWORD}),
            content_type="application/json",
            headers={"X-CSRFToken": token},
        )

        self.assertEqual(response.status_code, 200)
