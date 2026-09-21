"""Scenarios for signing in, written as Given / When / Then.

Sign-in is the only way into the application, so these cover what a wrong
attempt reveals as much as what a right one returns.
"""

import json

from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import Quota, User

CSRF_URL = "/api/auth/csrf"
LOGIN_URL = "/api/auth/login"
LOGOUT_URL = "/api/auth/logout"
ME_URL = "/api/auth/me"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"


class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters

    def given_a_user(self, **extra) -> User:
        return User.objects.create_user(EMAIL, PASSWORD, **extra)

    def login(self, email=EMAIL, password=PASSWORD):
        return self.client.post(
            LOGIN_URL,
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )

    def body(self, response) -> dict:
        return json.loads(response.content)


class SignInScenarios(AuthTestCase):
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
        # Given: an account, which gets a quota row when it is created
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


class SessionScenarios(AuthTestCase):
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


class CsrfScenarios(AuthTestCase):
    """The SPA is same-origin, so CSRF protection is on for every mutation."""

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


class AccountCreationScenarios(TestCase):
    def test_creating_a_user_creates_its_quota(self):
        user = User.objects.create_user(EMAIL, PASSWORD)

        self.assertTrue(Quota.objects.filter(user=user).exists())

    def test_an_address_cannot_be_registered_twice(self):
        User.objects.create_user(EMAIL, PASSWORD)

        with self.assertRaises(Exception):
            User.objects.create_user(EMAIL, PASSWORD)

    def test_superuser_is_staff(self):
        user = User.objects.create_superuser(EMAIL, PASSWORD)

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_name_falls_back_to_the_address_local_part(self):
        user = User.objects.create_user(EMAIL, PASSWORD)

        self.assertEqual(user.name, "person")
