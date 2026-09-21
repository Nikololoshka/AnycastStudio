"""People who use the application, and what each of them may consume.

Sign-up is deliberately absent: accounts are created through the Django admin,
which is never published. There is no email delivery, so there is no address
verification and no self-service password reset either.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("A user needs an email address")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        Quota.objects.create(user=user)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    locale = models.CharField(max_length=5, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    theme = models.CharField(max_length=16, default="system")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.email

    @property
    def name(self) -> str:
        return self.display_name or self.email.partition("@")[0]


def default_storage_bytes() -> int:
    return settings.MAX_STORAGE_BYTES


def default_media_asset_bytes() -> int:
    return settings.MAX_MEDIA_ASSET_BYTES


def default_concurrent_uploads() -> int:
    return settings.MAX_CONCURRENT_UPLOADS


def default_publications_per_day() -> int:
    return settings.MAX_PUBLICATIONS_PER_DAY


class Quota(models.Model):
    """What one user may consume. Defaults come from the Limits block in settings.

    A row is created with the user, so the limits of an existing account can be
    raised without touching anyone else's.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="quota")

    max_storage_bytes = models.BigIntegerField(default=default_storage_bytes)
    max_media_asset_bytes = models.BigIntegerField(default=default_media_asset_bytes)
    max_concurrent_uploads = models.PositiveSmallIntegerField(default=default_concurrent_uploads)
    max_publications_per_day = models.PositiveSmallIntegerField(default=default_publications_per_day)

    def __str__(self) -> str:
        return f"quota of {self.user.email}"
