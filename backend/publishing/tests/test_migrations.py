from importlib import import_module
from unittest import mock

from django.apps import apps

from publishing.models import PublicationTarget

from .base import PublishingTestCase

commit_marker = import_module("publishing.migrations.0003_commit_marker")


class CommitMarkerMigrationScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("publishing.tasks.run_target.delay")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.create_publication()

    def test_a_post_that_may_exist_keeps_its_protection_under_the_new_name(self):
        # Given: a target stored while the old X publisher marked a post in flight
        PublicationTarget.objects.update(resume_state={"posting_started": 1_700_000_000.0, "polls": 2})

        # When: the migration runs
        commit_marker.rename_commit_marker(apps, None)

        # Then: the mark is under the name the pipeline checks, and nothing else changed
        state = PublicationTarget.objects.get().resume_state
        self.assertEqual(state, {"commit_started": "2023-11-14T22:13:20+00:00", "polls": 2})

    def test_a_target_without_the_old_mark_is_left_alone(self):
        PublicationTarget.objects.update(resume_state={"session_uri": "https://upload.example/1", "offset": 10})

        commit_marker.rename_commit_marker(apps, None)

        self.assertEqual(PublicationTarget.objects.get().resume_state, {"session_uri": "https://upload.example/1", "offset": 10})
