from django.test import SimpleTestCase, override_settings

from config.wiring import container


class ContainerScenarios(SimpleTestCase):
    def test_a_changed_setting_reaches_the_platform_config(self):
        # Given: the container was built with the default chunk size
        before = container().config.upload.chunk_bytes

        # When: a setting is overridden
        with override_settings(PLATFORM_CHUNK_BYTES=before + 1):
            during = container().config.upload.chunk_bytes

        # Then: the override is seen inside and forgotten after
        self.assertEqual(during, before + 1)
        self.assertEqual(container().config.upload.chunk_bytes, before)

    def test_the_client_secret_stays_out_of_the_config_repr(self):
        # When: the config is printed
        printed = repr(container().config)

        # Then: no client secret appears in it
        self.assertNotIn("DO-NOT-LEAK", printed)
