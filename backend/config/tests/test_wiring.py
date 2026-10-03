from django.test import SimpleTestCase, override_settings

from config.wiring import container


class ContainerScenarios(SimpleTestCase):
    def test_a_changed_setting_reaches_the_platform_config(self):
        # Given: the container was built with the default chunk size
        before = container().platform_configs.youtube.chunk_bytes

        # When: a setting is overridden
        with override_settings(PLATFORM_CHUNK_BYTES=before + 1):
            during = container().platform_configs.youtube.chunk_bytes

        # Then: the override is seen inside and forgotten after
        self.assertEqual(during, before + 1)
        self.assertEqual(container().platform_configs.youtube.chunk_bytes, before)

    def test_the_redirect_goes_through_the_redirect_origin(self):
        with override_settings(PUBLIC_REDIRECT_ORIGIN="https://tunnel.example"):
            redirect = container().platform_configs.tiktok.redirect_uri

        self.assertEqual(redirect, "https://tunnel.example/api/social/tiktok/callback")

    def test_the_client_secret_stays_out_of_the_config_repr(self):
        # When: the config is printed
        printed = repr(container().platform_configs)

        # Then: no client secret appears in it
        self.assertNotIn("DO-NOT-LEAK", printed)
