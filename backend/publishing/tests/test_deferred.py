from unittest import mock

from django.utils import timezone

from platforms import PlatformCatalog
from platforms.core import PlatformType
from publishing.models import Publication, PublicationTarget
from services import tasks
from services.usecases.publications import DeferredDispatcher

from .base import PublishingTestCase

Status = PublicationTarget.Status


class DeferredStartScenarios(PublishingTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.tasks.run_target.delay")
        self.dispatch = patcher.start()
        self.addCleanup(patcher.stop)

    def given_platform_without_native_scheduling(self):
        patcher = mock.patch.object(PlatformCatalog, "deferring_upload", return_value=(PlatformType.YOUTUBE,))
        patcher.start()
        self.addCleanup(patcher.stop)

    def given_publication_at(self, when) -> PublicationTarget:
        self.create_publication(publishAt=(timezone.now() + timezone.timedelta(hours=1)).isoformat())
        Publication.objects.update(publish_at=when)
        self.dispatch.reset_mock()
        return self.only_target()

    def test_a_platform_with_native_scheduling_starts_uploading_at_once(self):
        # Given: a scheduled publication on a platform that schedules by itself
        when = timezone.now() + timezone.timedelta(hours=2)

        # When: it is created
        self.create_publication(publishAt=when.isoformat())

        # Then: the worker gets it now
        self.dispatch.assert_called_once()

    def test_a_deferred_platform_waits_for_the_publish_time(self):
        # Given: a platform that publishes when the upload ends
        self.given_platform_without_native_scheduling()
        when = timezone.now() + timezone.timedelta(hours=2)

        # When: a scheduled publication is created
        self.create_publication(publishAt=when.isoformat())

        # Then: nothing is handed to the worker yet
        self.dispatch.assert_not_called()
        self.assertEqual(self.only_target().status, Status.QUEUED)

    def test_a_deferred_publication_without_a_time_starts_at_once(self):
        # Given: a deferred platform
        self.given_platform_without_native_scheduling()

        # When: an immediate publication is created
        self.create_publication()

        # Then: the worker gets it now
        self.dispatch.assert_called_once()

    def test_the_sweep_leaves_a_target_whose_time_has_not_come(self):
        # Given: a deferred target due in an hour
        self.given_platform_without_native_scheduling()
        self.given_publication_at(timezone.now() + timezone.timedelta(hours=1))

        # When: the sweep runs
        dispatched = tasks.dispatch_due_targets()

        # Then: it stays waiting
        self.assertEqual(dispatched, 0)
        self.dispatch.assert_not_called()

    def test_the_sweep_hands_a_due_target_to_the_worker_once(self):
        # Given: a deferred target whose time has passed
        self.given_platform_without_native_scheduling()
        target = self.given_publication_at(timezone.now() - timezone.timedelta(minutes=1))

        # When: the sweep runs twice before the worker picks it up
        tasks.dispatch_due_targets()
        tasks.dispatch_due_targets()

        # Then: the worker got it once
        self.dispatch.assert_called_once_with(target.pk)

    def test_the_sweep_hands_it_again_when_the_worker_never_took_it(self):
        # Given: a due target dispatched long ago and still queued
        self.given_platform_without_native_scheduling()
        target = self.given_publication_at(timezone.now() - timezone.timedelta(hours=1))
        PublicationTarget.objects.filter(pk=target.pk).update(
            last_activity_at=timezone.now() - DeferredDispatcher.REDISPATCH_AFTER * 2
        )

        # When: the sweep runs
        tasks.dispatch_due_targets()

        # Then: it is handed to the worker again
        self.dispatch.assert_called_once_with(target.pk)

    def test_the_sweep_ignores_a_platform_with_native_scheduling(self):
        # Given: a due YouTube target still queued
        self.given_publication_at(timezone.now() - timezone.timedelta(minutes=1))

        # When: the sweep runs
        dispatched = tasks.dispatch_due_targets()

        # Then: the sweep does not touch it
        self.assertEqual(dispatched, 0)

    def test_retrying_a_deferred_target_before_its_time_waits(self):
        # Given: a failed deferred target due in an hour
        self.given_platform_without_native_scheduling()
        target = self.given_publication_at(timezone.now() + timezone.timedelta(hours=1))
        PublicationTarget.objects.filter(pk=target.pk).update(status=Status.FAILED)

        # When: it is retried
        self.client.post(f"/api/targets/{target.pk}/retry")

        # Then: it is queued but not handed to the worker
        target.refresh_from_db()
        self.assertEqual(target.status, Status.QUEUED)
        self.dispatch.assert_not_called()
