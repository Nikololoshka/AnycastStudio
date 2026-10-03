from importlib import import_module
from unittest import mock

from django.apps import apps

from publishing.models import PublicationTarget

from .base import PublishingTestCase

platform_failures = import_module("publishing.migrations.0004_confirmation_state_and_failures")


class PlatformFailureMigrationScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("publishing.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.create_publication()

    def test_a_stored_failure_is_told_in_the_platform_vocabulary(self):
        # Given: a target that failed before the failures were renamed
        PublicationTarget.objects.update(
            status="failed", error={"type": "validation", "message": "titleTooLong", "details": "titleTooLong"}
        )

        # When: the migration runs
        platform_failures.adopt_platform_failures(apps, None)

        # Then: the failure has its new name and keeps its words
        self.assertEqual(
            PublicationTarget.objects.get().error,
            {"failure": "invalid", "message": "titleTooLong", "details": "titleTooLong"},
        )

    def test_a_post_that_may_exist_stays_a_warning(self):
        message = "The post may have been created; check X before publishing again"
        PublicationTarget.objects.update(status="failed", error={"type": "platform", "message": message})

        platform_failures.adopt_platform_failures(apps, None)

        self.assertEqual(PublicationTarget.objects.get().error["failure"], "unconfirmed")

    def test_a_target_waiting_for_the_platform_keeps_its_confirmation_state(self):
        state = {"confirming_since": "2026-01-01T12:00:00+00:00", "polls": 2, "commit_started": "x"}
        PublicationTarget.objects.update(status="processing", confirmation_state=state)

        platform_failures.adopt_platform_failures(apps, None)

        self.assertEqual(PublicationTarget.objects.get().confirmation_state, state)

    def test_an_upload_resume_point_is_dropped(self):
        PublicationTarget.objects.update(status="uploading", confirmation_state={"session_uri": "https://u/1"})

        platform_failures.adopt_platform_failures(apps, None)

        self.assertIsNone(PublicationTarget.objects.get().confirmation_state)
