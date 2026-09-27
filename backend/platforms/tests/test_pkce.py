from django.test import SimpleTestCase

from platforms.oauth import pkce

RFC_7636_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


class ChallengeScenarios(SimpleTestCase):
    def test_the_standard_challenge_matches_rfc_7636(self):
        self.assertEqual(pkce.s256_challenge(RFC_7636_VERIFIER), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_the_hex_challenge_is_the_same_digest_in_lowercase_hex(self):
        self.assertEqual(
            pkce.hex_s256_challenge(RFC_7636_VERIFIER),
            "13d31e961a1ad8ec2f16b10c4c982e0876a878ad6df144566ee1894acb70f9c3",
        )
