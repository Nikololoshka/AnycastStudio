from platforms.http import AUTHENTICATION, RATE_LIMIT, VALIDATION, PlatformFailure, send
from platforms.upload import NeedsFreshToken, fresh_token_on_rejection

from .base import FakeResponse, PlatformTestCase

URL = "https://api.example.test/upload"


class SendScenarios(PlatformTestCase):
    def test_a_success_is_returned_as_is(self):
        # Given: the platform answers 200
        self.http.return_value = FakeResponse(200, {"id": "1"})

        # When: we send
        response = send("POST", URL, label="Example")

        # Then: the response comes back after one call
        self.assertEqual(response.json(), {"id": "1"})
        self.assertEqual(self.http.call_count, 1)

    def test_a_retryable_answer_is_sent_again(self):
        # Given: the platform is unavailable once, then answers
        self.http.side_effect = [FakeResponse(503), FakeResponse(200)]

        # When: we send
        response = send("POST", URL, label="Example")

        # Then: the second answer wins
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.http.call_count, 2)

    def test_a_platform_classifier_can_refuse_an_http_success(self):
        # Given: the platform hides a refusal inside a 200 body
        self.http.return_value = FakeResponse(200, {"error": "quota"})

        def failure_of(response):
            if response.json().get("error"):
                return PlatformFailure(RATE_LIMIT, "Quota exhausted", details="quota")
            return None

        # When: we send with that classifier
        with self.assertRaises(PlatformFailure) as raised:
            send("POST", URL, label="Example", failure_of=failure_of)

        # Then: its failure is raised without a retry
        self.assertEqual(raised.exception.type, RATE_LIMIT)
        self.assertEqual(raised.exception.details, "quota")
        self.assertEqual(self.http.call_count, 1)


class FakeState:
    def as_dict(self) -> dict:
        return {"offset": 42}


class FreshTokenScenarios(PlatformTestCase):
    def test_a_rejected_token_asks_for_a_fresh_one_with_the_state(self):
        # Given: an action the platform refuses as unauthenticated
        def action():
            raise PlatformFailure(AUTHENTICATION, "The connection expired")

        # When: it runs
        with self.assertRaises(NeedsFreshToken) as raised:
            fresh_token_on_rejection(action, FakeState())

        # Then: the state to resume from travels with it
        self.assertEqual(raised.exception.state, {"offset": 42})

    def test_a_rejection_without_state_carries_none(self):
        # Given: a refused action with no upload in progress
        def action():
            raise PlatformFailure(AUTHENTICATION, "The connection expired")

        # When: it runs
        with self.assertRaises(NeedsFreshToken) as raised:
            fresh_token_on_rejection(action)

        # Then: there is nothing to resume from
        self.assertIsNone(raised.exception.state)

    def test_other_failures_pass_through(self):
        # Given: an action refused for another reason
        def action():
            raise PlatformFailure(VALIDATION, "Bad file")

        # When / Then: the failure is not turned into a token refresh
        with self.assertRaises(PlatformFailure):
            fresh_token_on_rejection(action)
