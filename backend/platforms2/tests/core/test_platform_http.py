import aiohttp
from pydantic import BaseModel, Field

from platforms2.core import PlatformError, PlatformFailure, RetryPolicy
from platforms2.x.core import XHttp

from ..base import PlatformTestCase, ok
from ..fakes.http import FakeAnswer

URL = "https://api.example.com/thing"


class Thing(BaseModel):
    id: str = Field(min_length=1)


class PlatformHttpScenarios(PlatformTestCase):
    async def test_an_answer_becomes_its_model(self):
        # Given: the platform answers with the expected shape
        self.given_answers(ok({"id": "42", "extra": True}))

        # When: the answer is read
        thing = await XHttp(self.http).answer("GET", URL, Thing)

        # Then: it is the model, and the request went where it was asked to
        self.assertEqual(thing.id, "42")
        self.assertEqual((self.http.last.method, self.http.last.url), ("GET", URL))

    async def test_a_refusal_carries_the_platforms_classification_and_words(self):
        # Given: the platform refuses with its problem body
        self.given_answers(FakeAnswer(403, {"title": "Forbidden", "detail": "Not allowed to post"}))

        # When / Then: the failure is the platform's verdict, with its own words
        with self.assertRaises(PlatformError) as raised:
            await XHttp(self.http).answer("GET", URL, Thing)
        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)
        self.assertIn("Not allowed to post", raised.exception.message)

    async def test_an_unexpected_shape_is_unexpected(self):
        self.given_answers(ok({"id": ""}))

        with self.assertRaises(PlatformError) as raised:
            await XHttp(self.http).answer("GET", URL, Thing)

        self.assertEqual(raised.exception.failure, PlatformFailure.UNEXPECTED)

    async def test_a_body_that_is_not_json_is_read_as_empty(self):
        # Given: a proxy answers a 502 with an HTML page
        self.given_answers(FakeAnswer(502, "<html>Bad gateway</html>"))

        # When: the request is sent
        response = await XHttp(self.http).request("GET", URL)

        # Then: the body is empty, and the outage is transient
        self.assertEqual(response.body, {})
        self.assertEqual(response.failure(), PlatformFailure.NETWORK)
        self.assertEqual(response.refusal(), "HTTP 502")

    async def test_a_network_error_reports_only_its_class(self):
        # Given: the connection fails with a message that would carry the URL
        self.given_answers(aiohttp.ClientConnectionError(f"Cannot connect to {URL}?client_secret=s3cret"))

        # When / Then: the failure is transient and names only the class of the error
        with self.assertRaises(PlatformError) as raised:
            await XHttp(self.http).request("GET", URL)
        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)
        self.assertTrue(raised.exception.transient)
        self.assertNotIn("s3cret", raised.exception.message)
        self.assertIn("ClientConnectionError", raised.exception.message)

    async def test_a_timeout_is_a_network_failure(self):
        self.given_answers(TimeoutError())

        with self.assertRaises(PlatformError) as raised:
            await XHttp(self.http).request("GET", URL)

        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)


class RetryPolicyScenarios(PlatformTestCase):
    async def test_a_passing_outage_is_retried(self):
        # Given: the first attempt hits an outage, the second succeeds
        self.given_answers(FakeAnswer(503), ok({"id": "1"}))

        # When: the call runs under the policy
        thing = await RetryPolicy(2).run(lambda: XHttp(self.http).answer("GET", URL, Thing))

        # Then: the second answer is the result
        self.assertEqual(thing.id, "1")
        self.assertEqual(len(self.http.sent), 2)

    async def test_a_verdict_of_the_platform_is_not_retried(self):
        # Given: the platform refuses outright
        self.given_answers(FakeAnswer(400, {"title": "Bad request"}), ok({"id": "1"}))

        # When / Then: there is no second attempt
        with self.assertRaises(PlatformError):
            await RetryPolicy(3).run(lambda: XHttp(self.http).answer("GET", URL, Thing))
        self.assertEqual(len(self.http.sent), 1)

    async def test_retries_end_with_the_last_failure(self):
        # Given: the outage outlasts every retry
        self.given_answers(FakeAnswer(503), FakeAnswer(503), FakeAnswer(503))

        # When / Then: after the retries the outage is reported
        with self.assertRaises(PlatformError) as raised:
            await RetryPolicy(2).run(lambda: XHttp(self.http).answer("GET", URL, Thing))
        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)
        self.assertEqual(len(self.http.sent), 3)
