from django.core.management.base import BaseCommand

from media.services import sweep_unused_assets, sweep_upload_sessions


class Command(BaseCommand):
    help = "Abort stale upload sessions and delete media nothing needs any more."

    def handle(self, *args, **options):
        sessions = sweep_upload_sessions()
        assets = sweep_unused_assets()
        self.stdout.write(f"swept {sessions} upload sessions and {assets} assets")
