from platforms.core.errors import FailureType, PlatformError
from platforms.core.http import PlatformModel, ResponseParser

from .base import FakeResponse, PlatformTestCase

SECRET = "ya29.do-not-leak"


class Upload(PlatformModel):
    id: str
    offset: int = 0


class Token(PlatformModel):
    access_token: str
    expires_in: int


class NotJson(FakeResponse):
    def json(self):
        raise ValueError(SECRET)


class ParseScenarios(PlatformTestCase):
    def test_an_answer_becomes_its_model(self):
        # Given: the platform answers with the fields we need and more
        response = FakeResponse(200, {"id": "u1", "offset": "1024", "unused": True})

        # When: it is parsed
        upload = ResponseParser("Example").parse(response, Upload)

        # Then: numbers are coerced and unknown fields are ignored
        self.assertEqual(upload, Upload(id="u1", offset=1024))

    def test_a_numeric_id_is_kept_as_text(self):
        # When: the platform sends an id as a number
        upload = ResponseParser("Example").parse(FakeResponse(200, {"id": 17}), Upload)

        # Then: it is the same id as text
        self.assertEqual(upload.id, "17")

    def test_a_missing_required_field_raises_the_domain_refusal(self):
        # Given: the platform opened nothing
        response = FakeResponse(200, {"offset": 0})

        # When / Then: the refusal says what did not happen and which field was missing
        with self.assertRaises(PlatformError) as raised:
            ResponseParser("Example").parse(response, Upload, refusal="Example did not open an upload")
        self.assertEqual(raised.exception.type, FailureType.PLATFORM)
        self.assertEqual(raised.exception.message, "Example did not open an upload")
        self.assertEqual(raised.exception.details, "id")

    def test_without_a_refusal_the_platform_is_named(self):
        # When / Then: a generic message names the platform
        with self.assertRaisesMessage(PlatformError, "Example answered in an unexpected shape"):
            ResponseParser("Example").parse(FakeResponse(200, []), Upload)

    def test_a_body_that_is_not_json_is_refused(self):
        # When / Then: the refusal does not repeat what the body said
        with self.assertRaises(PlatformError) as raised:
            ResponseParser("Example").parse(NotJson(200), Upload)
        self.assertNotIn(SECRET, raised.exception.message)
        self.assertNotIn(SECRET, raised.exception.details)
        self.assertIsNone(raised.exception.__context__)

    def test_a_refused_token_answer_never_repeats_the_token(self):
        # Given: a token answer with a malformed field next to the token
        response = FakeResponse(200, {"access_token": SECRET, "expires_in": "soon"})

        # When: it is parsed
        with self.assertRaises(PlatformError) as raised:
            ResponseParser("Example").parse(response, Token)

        # Then: only the field path goes out, never the values
        self.assertEqual(raised.exception.details, "expires_in")
        self.assertNotIn(SECRET, raised.exception.message)
        self.assertIsNone(raised.exception.__context__)
