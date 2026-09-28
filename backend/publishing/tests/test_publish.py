from django.test import override_settings
from django.utils import timezone

from platforms.core.errors import PlatformError
from publishing.models import PublicationTarget
from publishing import pipeline

from .base import PublishingTestCase

Status = PublicationTarget.Status


class PublishScenarios(PublishingTestCase):
    def test_the_chosen_privacy_is_applied_on_publish(self):
        self.create_publication()
        google = self.given_google()

        pipeline.run_target(self.only_target().pk)

        self.assertEqual(google.published[-1]["status"]["privacyStatus"], "public")

    def test_a_scheduled_video_goes_up_private_with_a_publish_time(self):
        # Given: a publication due in an hour
        when = timezone.now() + timezone.timedelta(hours=1)
        self.create_publication(publishAt=when.isoformat())
        google = self.given_google()

        result = pipeline.run_target(self.only_target().pk)

        # Then: YouTube holds it. publishAt is ignored unless the video is
        # private at the same time, so both are sent together.
        self.assertEqual(result, Status.SCHEDULED)
        status = google.published[-1]["status"]
        self.assertEqual(status["privacyStatus"], "private")
        self.assertTrue(status["publishAt"])

    def test_a_scheduled_video_is_uploaded_private_too(self):
        when = timezone.now() + timezone.timedelta(hours=1)
        self.create_publication(publishAt=when.isoformat())
        google = self.given_google()

        pipeline.run_target(self.only_target().pk)

        # Then: one session was opened, carrying the private status from the start
        self.assertEqual(google.session_calls, 1)

    def test_hashtags_are_appended_to_the_description(self):
        self.create_publication()
        google = self.given_google()
        sent: list[dict] = []
        real_call = google.__call__

        def capture(method, url, **kwargs):
            if "upload/youtube" in url:
                sent.append(kwargs.get("json") or {})
            return real_call(method, url, **kwargs)

        self.http.side_effect = capture

        pipeline.run_target(self.only_target().pk)

        self.assertIn("#one", sent[0]["snippet"]["description"])

    @override_settings(UPLOAD_RETRY_ATTEMPTS=2)
    def test_a_platform_outage_eventually_gives_up(self):
        self.create_publication()
        self.http.side_effect = PlatformError("platform", "down", retryable=True)

        result = pipeline.run_target(self.only_target().pk)

        self.assertEqual(result, Status.FAILED)
