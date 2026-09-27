import json

from django.test import override_settings

from ..models import User
from .base import EMAIL, LOGIN_URL, PASSWORD, BaseAuthTestCase


class SignInScenarios(BaseAuthTestCase):
    def test_correct_credentials_start_a_session(self):
        # Given: an account exists
        self.given_a_user(display_name="Person")

        # When: the right password is sent
        response = self.login()

        # Then: the session cookie is set and the profile comes back
        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["user"]["email"], EMAIL)
        self.assertEqual(body["user"]["displayName"], "Person")
        self.assertIn("sessionid", response.cookies)

    def test_password_is_never_returned(self):
        self.given_a_user()
        body = self.body(self.login())
        self.assertNotIn("password", json.dumps(body))

    def test_quota_is_reported_with_the_profile(self):
        # Given: an account with the default limits
        self.given_a_user()

        # Then: the SPA can show what is left without a second request
        quota = self.body(self.login())["user"]["quota"]
        self.assertGreater(quota["maxStorageBytes"], 0)
        self.assertGreater(quota["maxMediaAssetBytes"], 0)

    def test_wrong_password_is_rejected(self):
        self.given_a_user()
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.body(response)["status"], "unauthorized")
        self.assertNotIn("sessionid", response.cookies)

    def test_unknown_address_answers_exactly_like_a_wrong_password(self):
        # Given: one account exists
        self.given_a_user()

        # When: an unknown address and a wrong password are each tried
        unknown = self.login(email="nobody@example.com")
        wrong = self.login(password="wrong")

        # Then: the responses are indistinguishable, so the endpoint does not
        # reveal which addresses are registered
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(self.body(unknown), self.body(wrong))

    def test_a_malformed_address_answers_like_a_wrong_password(self):
        # Given: one account exists
        self.given_a_user()

        # When: something that is not an address is tried
        malformed = self.login(email="not-an-address")
        wrong = self.login(password="wrong")

        # Then: it is not reported as a format error, which would say more
        self.assertEqual(malformed.status_code, 401)
        self.assertEqual(self.body(malformed), self.body(wrong))

    def test_the_address_is_matched_regardless_of_case(self):
        # Given: an account created with a mixed-case address
        User.objects.create_user("Person@Example.COM", PASSWORD)

        # When: the person signs in typing it in lower case
        response = self.login(email="person@example.com")

        # Then: it is the same account
        self.assertEqual(response.status_code, 200)

    def test_inactive_account_cannot_sign_in(self):
        user = self.given_a_user()
        user.is_active = False
        user.save()

        self.assertEqual(self.login().status_code, 401)

    def test_malformed_body_is_reported_per_field(self):
        response = self.client.post(LOGIN_URL, data=json.dumps({"email": EMAIL}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        body = self.body(response)
        self.assertEqual(body["status"], "invalid")
        self.assertEqual([error["field"] for error in body["errors"]], ["password"])

    def test_body_that_is_not_json_is_reported(self):
        response = self.client.post(LOGIN_URL, data="not json", content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["status"], "invalid")

    def test_get_is_not_allowed(self):
        response = self.client.get(LOGIN_URL)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers["Allow"], "POST")

    @override_settings(RATE_LIMITS={"login": (2, 60)})
    def test_repeated_attempts_are_rate_limited(self):
        # Given: an account, and a limit of two attempts
        self.given_a_user()

        # When: the wrong password is tried three times
        self.login(password="wrong")
        self.login(password="wrong")
        third = self.login(password="wrong")

        # Then: the third is refused before the password is even checked
        self.assertEqual(third.status_code, 429)
        self.assertEqual(self.body(third)["status"], "rate_limited")
