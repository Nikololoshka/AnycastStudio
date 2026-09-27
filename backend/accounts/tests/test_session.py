from .base import CSRF_URL, EMAIL, LOGOUT_URL, ME_URL, BaseAuthTestCase


class SessionScenarios(BaseAuthTestCase):
    def test_me_requires_a_session(self):
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.body(response)["status"], "unauthorized")

    def test_me_returns_the_signed_in_user(self):
        self.given_a_user()
        self.login()

        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response)["user"]["email"], EMAIL)

    def test_logout_ends_the_session(self):
        self.given_a_user()
        self.login()

        self.client.post(LOGOUT_URL)

        self.assertEqual(self.client.get(ME_URL).status_code, 401)

    def test_logout_requires_a_session(self):
        self.assertEqual(self.client.post(LOGOUT_URL).status_code, 401)

    def test_csrf_endpoint_seeds_the_cookie(self):
        response = self.client.get(CSRF_URL)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["csrfToken"])
        self.assertIn("csrftoken", response.cookies)
