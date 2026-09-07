import unittest
from pathlib import Path

from dolls_orchestrator.config import ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_offline_profile_does_not_require_api_key(self):
        settings = Settings.from_env({})
        self.assertEqual("offline", settings.profile)
        self.assertIsNone(settings.deepseek_api_key)
        self.assertFalse(settings.deepseek_network_enabled)

    def test_environment_overrides_are_parsed(self):
        settings = Settings.from_env(
            {
                "DOLLS_PROFILE": "offline-macos",
                "DOLLS_CONTEXT_TURNS": "3",
                "DOLLS_DEEPSEEK_NETWORK_ENABLED": "yes",
                "DEEPSEEK_API_KEY": "secret-value",
                "DOLLS_CHARACTER_PACKAGE_PATH": "/tmp/test-character",
            }
        )
        self.assertEqual(3, settings.context_turns)
        self.assertTrue(settings.deepseek_network_enabled)
        self.assertEqual("secret-value", settings.deepseek_api_key)
        self.assertNotIn("secret-value", repr(settings))
        self.assertEqual(Path("/tmp/test-character"), settings.character_package_path)

    def test_invalid_values_fail_fast(self):
        for environment in (
            {"DOLLS_CONTEXT_TURNS": "0"},
            {"DOLLS_ASR_TIMEOUT_SECONDS": "invalid"},
            {"DOLLS_DEEPSEEK_NETWORK_ENABLED": "maybe"},
            {"DOLLS_LLM_BASE_URL": "http://insecure.example"},
        ):
            with self.subTest(environment=environment):
                with self.assertRaises(ConfigurationError):
                    Settings.from_env(environment)

    def test_local_no_api_profile_is_valid(self):
        settings = Settings.from_env({"DOLLS_PROFILE": "local-no-api"})
        self.assertEqual("local-no-api", settings.profile)

    def test_character_package_is_optional(self):
        self.assertIsNone(Settings.from_env({}).character_package_path)


if __name__ == "__main__":
    unittest.main()
