from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase

from ..models import User
from .base import EMAIL, PASSWORD


class AccountCreationScenarios(TestCase):
    def test_limits_start_from_the_settings(self):
        user = User.objects.create_user(EMAIL, PASSWORD)

        self.assertEqual(user.max_storage_bytes, settings.MAX_STORAGE_BYTES)
        self.assertEqual(user.max_media_asset_bytes, settings.MAX_MEDIA_ASSET_BYTES)
        self.assertEqual(user.max_concurrent_uploads, settings.MAX_CONCURRENT_UPLOADS)
        self.assertEqual(user.max_publications_per_day, settings.MAX_PUBLICATIONS_PER_DAY)

    def test_an_address_cannot_be_registered_twice(self):
        User.objects.create_user(EMAIL, PASSWORD)

        with self.assertRaises(IntegrityError):
            User.objects.create_user(EMAIL, PASSWORD)

    def test_an_address_differing_only_in_case_is_the_same_address(self):
        User.objects.create_user(EMAIL, PASSWORD)

        with self.assertRaises(IntegrityError):
            User.objects.create_user(EMAIL.upper(), PASSWORD)

    def test_addresses_are_stored_in_lower_case(self):
        user = User.objects.create_user("  Person@Example.COM ", PASSWORD)

        self.assertEqual(user.email, "person@example.com")

    def test_superuser_is_staff(self):
        user = User.objects.create_superuser(EMAIL, PASSWORD)

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_name_falls_back_to_the_address_local_part(self):
        user = User.objects.create_user(EMAIL, PASSWORD)

        self.assertEqual(user.name, "person")
