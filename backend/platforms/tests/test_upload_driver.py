from dataclasses import dataclass

from platforms.core.errors import FailureType, PlatformError
from platforms.upload import ResumableState, UploadCancelled, drive, read_piece

from .base import CHUNK, CONTENT, PlatformTestCase


@dataclass
class FakeState(ResumableState):
    upload_id: str
    offset: int = 0
    created_at: float = 0


class ResumableStateScenarios(PlatformTestCase):
    def test_a_stored_state_comes_back_as_it_was(self):
        # Given: a state written to resume_state
        stored = FakeState(upload_id="u1", offset=2048, created_at=10.5).as_dict()

        # When: it is read back
        state = FakeState.of(stored)

        # Then: every field survives the round trip
        self.assertEqual(state, FakeState(upload_id="u1", offset=2048, created_at=10.5))

    def test_values_are_cast_to_the_field_types(self):
        # Given: a state whose numbers arrived as strings
        raw = {"upload_id": 7, "offset": "1024", "created_at": "3"}

        # When: it is read
        state = FakeState.of(raw)

        # Then: each value has its declared type
        self.assertEqual(state, FakeState(upload_id="7", offset=1024, created_at=3.0))

    def test_missing_optional_fields_take_their_defaults(self):
        # When: only the required field is stored
        state = FakeState.of({"upload_id": "u1"})

        # Then: the rest start from zero
        self.assertEqual(state, FakeState(upload_id="u1"))

    def test_a_state_without_its_required_field_is_not_resumed(self):
        # When / Then: nothing to resume from
        self.assertIsNone(FakeState.of({"offset": 1024}))
        self.assertIsNone(FakeState.of({"upload_id": "", "offset": 1024}))

    def test_a_state_that_is_not_a_dict_is_not_resumed(self):
        # When / Then: stored garbage starts a new upload
        self.assertIsNone(FakeState.of(None))
        self.assertIsNone(FakeState.of(["u1"]))

    def test_a_value_of_the_wrong_type_is_not_resumed(self):
        # When / Then: a corrupted number starts a new upload instead of crashing
        self.assertIsNone(FakeState.of({"upload_id": "u1", "offset": "half"}))


class FakeSession:
    def __init__(self, size: int):
        self.state = FakeState(upload_id="u1")
        self.size = size
        self.pieces: list[bytes] = []

    @property
    def done(self) -> bool:
        return self.state.offset >= self.size

    @property
    def uploaded(self) -> int:
        return self.state.offset

    def send_next(self, handle) -> None:
        length = min(CHUNK, self.size - self.state.offset)
        self.pieces.append(read_piece(handle, self.state.offset, length))
        self.state.offset += length

    def finish(self) -> str:
        return self.state.upload_id


class DriveScenarios(PlatformTestCase):
    def test_the_file_is_sent_piece_by_piece_and_progress_is_reported(self):
        # Given: a file of five chunks
        session = FakeSession(len(CONTENT))
        reports = []

        # When: it is driven to the end
        media_id = drive(
            session,
            path=self.given_file(),
            size=len(CONTENT),
            on_progress=lambda uploaded, total, state: reports.append((uploaded, state["offset"])),
        )

        # Then: every piece went out and progress carried the stored state
        self.assertEqual(media_id, "u1")
        self.assertEqual(b"".join(session.pieces), CONTENT)
        self.assertEqual(reports, [(offset, offset) for offset in range(CHUNK, len(CONTENT) + 1, CHUNK)])

    def test_a_cancel_stops_before_the_next_piece_with_the_state_to_resume(self):
        # Given: a cancel requested after two pieces
        session = FakeSession(len(CONTENT))

        # When: the upload runs
        with self.assertRaises(UploadCancelled) as raised:
            drive(
                session,
                path=self.given_file(),
                size=len(CONTENT),
                should_cancel=lambda: len(session.pieces) == 2,
            )

        # Then: it stopped there and knows where to continue
        self.assertEqual(len(session.pieces), 2)
        self.assertEqual(raised.exception.state["offset"], 2 * CHUNK)

    def test_a_file_shorter_than_claimed_is_refused(self):
        # Given: a file that ends before the size we were told
        session = FakeSession(len(CONTENT) + CHUNK)

        # When: the upload reaches the missing bytes
        with self.assertRaises(PlatformError) as raised:
            drive(session, path=self.given_file(), size=len(CONTENT) + CHUNK)

        # Then: the refusal names the file
        self.assertEqual(raised.exception.type, FailureType.FILE)
