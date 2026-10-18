import json

from .base import ME_URL, BaseAuthTestCase

PREFERENCES_URL = f"{ME_URL}/preferences"


class PreferenceScenarios(BaseAuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.given_a_user()
        self.client.force_login(self.user)

    def update(self, **fields):
        return self.client.patch(PREFERENCES_URL, data=json.dumps(fields), content_type="application/json")

    def me(self) -> dict:
        return self.body(self.client.get(ME_URL))["user"]

    def test_a_new_person_keeps_files_thirty_days_and_starts_on_every_platform(self):
        user = self.me()

        self.assertEqual(user["mediaRetentionDays"], 30)
        self.assertEqual(user["defaultPlatforms"], ["youtube", "tiktok", "instagram", "x"])
        self.assertEqual(user["platformDefaults"]["x"]["replyAudience"], "everyone")
        self.assertIsNone(user["platformDefaults"]["tiktok"]["privacyLevel"])

    def test_the_retention_can_be_changed_or_turned_off(self):
        self.assertEqual(self.body(self.update(mediaRetentionDays=90))["user"]["mediaRetentionDays"], 90)

        self.update(mediaRetentionDays=None)

        self.assertIsNone(self.me()["mediaRetentionDays"])

    def test_a_retention_the_app_does_not_offer_is_refused(self):
        response = self.update(mediaRetentionDays=2)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.me()["mediaRetentionDays"], 30)

    def test_the_default_platforms_and_their_settings_are_kept(self):
        self.update(defaultPlatforms=["x"], platformDefaults={"x": {"replyAudience": "following"}})

        user = self.me()
        self.assertEqual(user["defaultPlatforms"], ["x"])
        self.assertEqual(user["platformDefaults"]["x"]["replyAudience"], "following")
        self.assertFalse(user["platformDefaults"]["x"]["madeWithAi"])

    def test_an_empty_selection_is_kept_rather_than_reset_to_all(self):
        self.update(defaultPlatforms=[])

        self.assertEqual(self.me()["defaultPlatforms"], [])

    def test_a_field_left_out_is_not_touched(self):
        # Given: a person who turned retention off
        self.update(mediaRetentionDays=None)

        # When: only the platforms change
        self.update(defaultPlatforms=["youtube"])

        # Then: retention stays off rather than falling back to a default
        self.assertIsNone(self.me()["mediaRetentionDays"])

    def test_an_unknown_platform_is_refused(self):
        self.assertEqual(self.update(defaultPlatforms=["myspace"]).status_code, 400)
        self.assertEqual(self.update(platformDefaults={"myspace": {}}).status_code, 400)

    def test_a_setting_the_platform_does_not_have_is_refused(self):
        response = self.update(platformDefaults={"youtube": {"privacyStatus": "secret"}})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.me()["platformDefaults"]["youtube"]["privacyStatus"], "private")

    def test_language_theme_and_time_zone_are_not_changed_here(self):
        self.update(locale="ru", theme="dark", timezone="Europe/Moscow")

        user = self.me()
        self.assertEqual((user["locale"], user["theme"], user["timezone"]), ("en", "system", "UTC"))

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.update(mediaRetentionDays=7).status_code, 401)
