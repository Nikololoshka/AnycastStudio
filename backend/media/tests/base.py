import hashlib
import json
import shutil
import tempfile

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import User
from media.models import MediaAsset

START_URL = "/api/media/uploads"
ASSETS_URL = "/api/media/assets"

EMAIL = "person@example.com"
PASSWORD = "correct-horse-battery"
OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "another-password-99"

CHUNK_SIZE = 1024
CONTENT = bytes(range(256)) * 20


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class UploadTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix="anycast-test-media-")
        cls.override = override_settings(MEDIA_ROOT=cls.media_root, UPLOAD_CHUNK_BYTES=CHUNK_SIZE)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(EMAIL, PASSWORD)
        self.client.force_login(self.user)

    def sign_in_as_someone_else(self) -> User:
        other = User.objects.create_user(OTHER_EMAIL, OTHER_PASSWORD)
        self.client.force_login(other)
        return other

    def body(self, response) -> dict:
        return json.loads(response.content)

    def start(self, size=len(CONTENT), checksum=None, filename="clip.mp4"):
        return self.client.post(
            START_URL,
            data=json.dumps(
                {
                    "filename": filename,
                    "sizeBytes": size,
                    "mimeType": "video/mp4",
                    "sha256": sha256_of(CONTENT) if checksum is None else checksum,
                }
            ),
            content_type="application/json",
        )

    def started_upload_id(self, **kwargs) -> str:
        return self.body(self.start(**kwargs))["uploadId"]

    def send_chunk(self, upload_id, data: bytes, offset: int):
        return self.client.patch(
            f"{START_URL}/{upload_id}",
            data=data,
            content_type="application/octet-stream",
            headers={"Upload-Offset": str(offset)},
        )

    def send_all(self, upload_id, content=CONTENT):
        offset = 0
        while offset < len(content):
            piece = content[offset : offset + CHUNK_SIZE]
            response = self.send_chunk(upload_id, piece, offset)
            offset = self.body(response)["offset"]
        return offset

    def complete(self, upload_id, **fields):
        return self.client.post(
            f"{START_URL}/{upload_id}/complete",
            data=json.dumps(fields),
            content_type="application/json",
        )

    def given_an_asset(self) -> MediaAsset:
        upload_id = self.started_upload_id()
        self.send_all(upload_id)
        self.complete(upload_id)
        return MediaAsset.objects.get()

    def given_a_publication_of(self, asset: MediaAsset, finished_at=None):
        from publishing.models import Publication, PublicationTarget
        from social.models import SocialAccount

        account = SocialAccount.objects.create(user=self.user, platform="youtube", external_id="UC_channel")
        publication = Publication.objects.create(user=self.user, asset=asset, title="A clip")
        return PublicationTarget.objects.create(
            publication=publication, platform="youtube", social_account=account, finished_at=finished_at
        )
