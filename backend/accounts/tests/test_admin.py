import json

from django.core.cache import cache
from django.test import TestCase

from ..models import User
from .base import EMAIL, LOGIN_URL, PASSWORD


class AdminAccountScenarios(TestCase):
    ADD_URL = "/admin/accounts/user/add/"

    def setUp(self):
        cache.clear()
        admin = User.objects.create_superuser("admin@example.com", PASSWORD)
        self.client.force_login(admin)

    def add_through_the_admin(self, email):
        return self.client.post(
            self.ADD_URL,
            {"email": email, "password1": PASSWORD, "password2": PASSWORD, "usable_password": "true"},
        )

    def test_a_person_added_in_the_admin_can_sign_in(self):
        self.add_through_the_admin(EMAIL)
        self.client.logout()

        response = self.client.post(
            LOGIN_URL,
            data=json.dumps({"email": EMAIL, "password": PASSWORD}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

    def test_the_admin_refuses_an_address_that_differs_only_in_case(self):
        # Given: an account already exists
        User.objects.create_user(EMAIL, PASSWORD)

        # When: the same address is added again in upper case
        response = self.add_through_the_admin(EMAIL.upper())

        # Then: the form reports it instead of failing on the database
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["adminform"].form.errors)
