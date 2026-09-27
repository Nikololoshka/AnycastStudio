from django.conf import settings
from django.urls import reverse


def callback_url(platform: str) -> str:
    return f"{settings.PUBLIC_REDIRECT_ORIGIN}{reverse('social-callback', args=[platform])}"
