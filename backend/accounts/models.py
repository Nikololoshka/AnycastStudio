from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from .fields import LowercaseEmailField


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("A user needs an email address")
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = LowercaseEmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    locale = models.CharField(max_length=5, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    theme = models.CharField(max_length=16, default="system")

    max_storage_bytes = models.BigIntegerField(default=settings.MAX_STORAGE_BYTES)
    max_media_asset_bytes = models.BigIntegerField(default=settings.MAX_MEDIA_ASSET_BYTES)
    max_concurrent_uploads = models.PositiveSmallIntegerField(default=settings.MAX_CONCURRENT_UPLOADS)
    max_publications_per_day = models.PositiveSmallIntegerField(default=settings.MAX_PUBLICATIONS_PER_DAY)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.email

    @property
    def name(self) -> str:
        return self.display_name or self.email.partition("@")[0]
