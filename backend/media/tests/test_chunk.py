import io

from media import services, storage
from media.models import MediaAsset, UploadSession

from .base import CHUNK_SIZE, CONTENT, START_URL, UploadTestCase, sha256_of


class CountingStream(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size=-1):
        piece = super().read(size)
        self.bytes_read += len(piece)
        return piece


class ChunkScenarios(UploadTestCase):
    def test_chunks_accumulate_and_the_server_reports_the_offset(self):
        upload_id = self.started_upload_id()

        first = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        second = self.send_chunk(upload_id, CONTENT[CHUNK_SIZE : CHUNK_SIZE * 2], CHUNK_SIZE)

        self.assertEqual(self.body(first)["offset"], CHUNK_SIZE)
        self.assertEqual(self.body(second)["offset"], CHUNK_SIZE * 2)

    def test_a_chunk_at_the_wrong_offset_is_refused_with_the_right_one(self):
        # Given: a transfer that already received one chunk
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # When: the client resends from a stale position, as it would after a
        # connection dropped mid-chunk
        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # Then: it is told where the server actually is, and nothing is appended
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["offset"], CHUNK_SIZE)
        self.assertEqual(UploadSession.objects.get().received_bytes, CHUNK_SIZE)

    def test_a_chunk_repeated_while_the_first_is_still_written_does_not_corrupt_the_file(self):
        # Given: two requests for the same chunk, both holding the session as it was before either landed
        upload_id = self.started_upload_id()
        first_copy = UploadSession.objects.get(upload_id=upload_id)
        second_copy = UploadSession.objects.get(upload_id=upload_id)
        services.receive_chunk(first_copy, 0, io.BytesIO(CONTENT[:CHUNK_SIZE]))

        # When: the repeat arrives
        with self.assertRaises(services.OffsetConflict) as conflict:
            services.receive_chunk(second_copy, 0, io.BytesIO(CONTENT[:CHUNK_SIZE]))

        # Then: it is refused with the real offset, and the bytes are still the right ones in the right place
        self.assertEqual(conflict.exception.offset, CHUNK_SIZE)
        self.send_all_from(upload_id, CHUNK_SIZE)
        self.complete(upload_id)
        self.assertEqual(MediaAsset.objects.get().sha256, sha256_of(CONTENT))

    def send_all_from(self, upload_id, offset: int):
        while offset < len(CONTENT):
            offset = self.body(self.send_chunk(upload_id, CONTENT[offset : offset + CHUNK_SIZE], offset))["offset"]

    def test_a_transfer_resumes_from_the_reported_offset(self):
        # Given: a transfer interrupted halfway
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        # When: the client asks where to continue and sends the rest
        offset = self.body(self.client.get(f"{START_URL}/{upload_id}/status"))["offset"]
        self.send_all_from(upload_id, offset)

        # Then: the file is whole and its checksum matches
        self.complete(upload_id)
        asset = MediaAsset.objects.get()
        self.assertEqual(asset.size_bytes, len(CONTENT))
        self.assertEqual(asset.sha256, sha256_of(CONTENT))

    def test_more_bytes_than_declared_abort_the_transfer(self):
        upload_id = self.started_upload_id(size=CHUNK_SIZE)

        response = self.send_chunk(upload_id, CONTENT[: CHUNK_SIZE * 2], 0)

        session = UploadSession.objects.get()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(session.status, UploadSession.Status.ABORTED)
        self.assertFalse(storage.absolute(session.storage_path).exists())

    def test_an_oversized_body_is_not_read_past_the_declared_size(self):
        # Given: a transfer declared as one chunk, and a body far larger than that
        session = UploadSession.objects.get(upload_id=self.started_upload_id(size=CHUNK_SIZE))
        body = CountingStream(b"x" * (CHUNK_SIZE * 100))

        # When: it is received
        with self.assertRaises(services.MoreBytesThanDeclared):
            services.receive_chunk(session, 0, body)

        # Then: reading stopped one byte past what was declared
        self.assertEqual(body.bytes_read, CHUNK_SIZE + 1)

    def test_a_missing_offset_header_is_refused(self):
        upload_id = self.started_upload_id()

        response = self.client.patch(
            f"{START_URL}/{upload_id}",
            data=CONTENT[:CHUNK_SIZE],
            content_type="application/octet-stream",
        )

        self.assertEqual(response.status_code, 400)

    def test_another_persons_transfer_is_not_found(self):
        upload_id = self.started_upload_id()
        self.sign_in_as_someone_else()

        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)

        self.assertEqual(response.status_code, 404)

    def test_a_stale_transfer_is_expired(self):
        # Given: a transfer nobody touched for longer than its time to live
        upload_id = self.started_upload_id()
        self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], 0)
        UploadSession.objects.update(last_activity_at=UploadSession.stale_cutoff())

        # When / Then: the next chunk is refused as expired
        response = self.send_chunk(upload_id, CONTENT[:CHUNK_SIZE], CHUNK_SIZE)

        self.assertEqual(response.status_code, 410)

    def test_put_is_not_allowed_on_the_chunk_endpoint(self):
        upload_id = self.started_upload_id()

        response = self.client.put(f"{START_URL}/{upload_id}", data=b"x")

        self.assertEqual(response.status_code, 405)
