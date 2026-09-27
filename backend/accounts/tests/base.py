import json

from django.core.cache import cache
from django.test import TestCase

from ..models import User

CSRF_URL = "/api/auth/csrf"
LOGIN_URL = "/api/auth/login"
LOGOUT_URL = "/api/auth/logout"
ME_URL = "/api/auth/me"
EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"


class BaseAuthTestCase(TestCase):
    def setUp(self):
        cache.clear()

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
