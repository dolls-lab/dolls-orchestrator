from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dolls_orchestrator.adapters.deepseek import DeepSeekLLMAdapter
from dolls_orchestrator.adapters.macos_tts import MacOSSayTTSAdapter
from dolls_orchestrator.adapters.mlx_whisper import MLXWhisperAdapter
from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.cli import main
from dolls_orchestrator.config import Settings
from dolls_orchestrator.health import check_service_health


class UnusedTransport:
    def __init__(self):
        self.calls = 0

    async def stream(self, request):
        self.calls += 1
        if False:
            yield ""


class AdapterHealthTests(unittest.TestCase):
    def test_offline_adapters_are_ready_without_primary_operations(self):
        health = [
            OfflineASRAdapter("unused").health(),
            OfflineLLMAdapter("unused").health(),
            ToneTTSAdapter().health(),
        ]
        self.assertEqual(["asr", "llm", "tts"], [item.stage for item in health])
        self.assertTrue(all(item.ready for item in health))

    def test_mlx_reports_missing_dependency_and_injected_runner_is_ready(self):
        adapter = MLXWhisperAdapter("test-model")
        with mock.patch(
            "dolls_orchestrator.adapters.mlx_whisper.importlib.util.find_spec",
            return_value=None,
        ):
            health = adapter.health()
        self.assertFalse(health.ready)
        self.assertEqual("dependency_missing_mlx_whisper", health.reason)

        injected = MLXWhisperAdapter("test-model", runner=lambda path, model: {})
        with mock.patch(
            "dolls_orchestrator.adapters.mlx_whisper.importlib.util.find_spec",
            side_effect=AssertionError("import discovery must be skipped"),
        ):
            self.assertTrue(injected.health().ready)

    def test_macos_reports_missing_command_and_injected_runner_is_ready(self):
        adapter = MacOSSayTTSAdapter()
        with mock.patch(
            "dolls_orchestrator.adapters.macos_tts.shutil.which",
            side_effect=lambda name: None if name == "afconvert" else "/usr/bin/" + name,
        ):
            health = adapter.health()
        self.assertFalse(health.ready)
        self.assertEqual("command_missing_afconvert", health.reason)

        async def runner(command):
            raise AssertionError("health must not run commands")

        self.assertTrue(MacOSSayTTSAdapter(command_runner=runner).health().ready)

    def test_deepseek_health_never_calls_transport_or_exposes_key(self):
        transport = UnusedTransport()
        adapter = DeepSeekLLMAdapter(
            api_key="health-test-secret",
            base_url="https://api.deepseek.com",
            model="test-model",
            network_enabled=False,
            max_output_tokens=10,
            transport=transport,
        )
        health = adapter.health()
        self.assertEqual("network_disabled", health.reason)
        self.assertEqual(0, transport.calls)
        self.assertNotIn("health-test-secret", json.dumps(health.to_dict()))

        adapter.network_enabled = True
        self.assertTrue(adapter.health().ready)
        self.assertEqual(0, transport.calls)

        missing = DeepSeekLLMAdapter(
            api_key=None,
            base_url="https://api.deepseek.com",
            model="test-model",
            network_enabled=True,
            max_output_tokens=10,
            transport=transport,
        )
        self.assertEqual("credential_missing", missing.health().reason)


class ServiceHealthTests(unittest.TestCase):
    def test_offline_report_is_ready_in_stable_order(self):
        report = check_service_health("offline", Settings())
        self.assertTrue(report.ready)
        self.assertEqual(
            ["character", "asr", "llm", "tts"],
            [component.stage for component in report.components],
        )
        self.assertEqual("builtin-v1", report.components[0].model)
        self.assertEqual("ready", report.to_dict()["status"])

    def test_invalid_character_is_generic_and_other_checks_continue(self):
        settings = Settings(character_package_path=Path("/missing/character-package"))
        report = check_service_health("offline", settings)
        self.assertFalse(report.ready)
        self.assertEqual("package_invalid", report.components[0].reason)
        self.assertTrue(all(component.ready for component in report.components[1:]))
        serialized = json.dumps(report.to_dict())
        self.assertNotIn("/missing/character-package", serialized)

    def test_local_voice_cli_is_blocked_without_network_and_keeps_key_secret(self):
        secret = "deepseek-health-secret"
        stdout = io.StringIO()
        with mock.patch.dict(
            "os.environ",
            {"DEEPSEEK_API_KEY": secret, "DOLLS_DEEPSEEK_NETWORK_ENABLED": "false"},
            clear=True,
        ), redirect_stdout(stdout):
            self.assertEqual(1, main(["health", "--profile", "local-voice"]))
        payload = json.loads(stdout.getvalue())
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("network_disabled", payload["components"][2]["reason"])
        self.assertNotIn(secret, stdout.getvalue())

    def test_local_no_api_cli_can_report_ready_from_discovery_only(self):
        stdout = io.StringIO()
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch(
            "dolls_orchestrator.adapters.mlx_whisper.importlib.util.find_spec",
            return_value=object(),
        ), mock.patch(
            "dolls_orchestrator.adapters.macos_tts.shutil.which",
            return_value="/usr/bin/tool",
        ), redirect_stdout(stdout):
            self.assertEqual(0, main(["health", "--profile", "local-no-api"]))
        self.assertEqual("ready", json.loads(stdout.getvalue())["status"])

    def test_explicit_invalid_character_cli_returns_one_with_report(self):
        stdout = io.StringIO()
        with mock.patch.dict("os.environ", {}, clear=True), redirect_stdout(stdout):
            self.assertEqual(1, main([
                "health",
                "--profile", "offline",
                "--character-package", "/missing/character",
            ]))
        payload = json.loads(stdout.getvalue())
        self.assertEqual("package_invalid", payload["components"][0]["reason"])

    def test_invalid_configuration_keeps_exit_two_semantics(self):
        stderr = io.StringIO()
        with mock.patch.dict(
            "os.environ", {"DOLLS_PROFILE": "invalid"}, clear=True
        ), redirect_stderr(stderr):
            self.assertEqual(2, main(["health"]))
        self.assertIn("DOLLS_PROFILE", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
