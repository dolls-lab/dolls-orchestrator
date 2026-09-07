import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.benchmark import (
    BenchmarkReport,
    BenchmarkTurnRecord,
    percentile_summary,
    run_benchmark,
    write_benchmark_report,
)
from dolls_orchestrator.character import BUILTIN_CHARACTER
from dolls_orchestrator.cli import main
from dolls_orchestrator.config import Settings
from dolls_orchestrator.domain import StageTelemetry, TurnTelemetry
from dolls_orchestrator.errors import (
    BenchmarkExecutionError,
    ProviderUnavailableError,
    TurnCancelledError,
)
from dolls_orchestrator.orchestrator import TurnOrchestrator

from tests.helpers import write_silent_wav


def _telemetry(status, first_audio_ms=None, total_ms=10, error_type=None):
    return TurnTelemetry(
        session_id="private-session",
        turn_id="private-turn",
        generation_id="private-generation",
        character_id="march-7th",
        character_version="0.1.0",
        status=status,
        first_audio_ms=first_audio_ms,
        total_ms=total_ms,
        stages={
            "asr": StageTelemetry(
                provider="offline", model="fixed", elapsed_ms=1
            )
        },
        error_stage="asr" if error_type else None,
        error_type=error_type,
    )


class ScriptedOrchestrator:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.last_telemetry = None
        self.character = BUILTIN_CHARACTER

    async def run_turn(self, input_path, session_id):
        telemetry = next(self.outcomes)
        self.last_telemetry = telemetry
        if telemetry.status == "failed":
            raise ProviderUnavailableError("private failure detail", stage="asr")
        if telemetry.status == "cancelled":
            raise TurnCancelledError()
        return mock.Mock(telemetry=telemetry)


class BenchmarkMetricTests(unittest.TestCase):
    def test_nearest_rank_percentiles_are_deterministic(self):
        self.assertEqual(
            {"samples": 4, "p50": 2.0, "p95": 4.0},
            percentile_summary([4, 1, 3, 2]),
        )
        self.assertEqual(
            {"samples": 0, "p50": None, "p95": None},
            percentile_summary([]),
        )

    def test_summary_counts_success_latency_and_immediate_recovery(self):
        report = BenchmarkReport(
            profile="offline",
            character_id="march-7th",
            character_version="0.1.0",
            turns=(
                BenchmarkTurnRecord(1, _telemetry("completed", 5, 10)),
                BenchmarkTurnRecord(
                    2, _telemetry("failed", None, 7, "ProviderUnavailableError")
                ),
                BenchmarkTurnRecord(3, _telemetry("completed", 9, 20)),
            ),
        )
        summary = report.summary()
        self.assertEqual(0.666667, summary["success_rate"])
        self.assertEqual(
            {"samples": 2, "p50": 5.0, "p95": 9.0},
            summary["first_audio_ms"],
        )
        self.assertEqual(1, summary["recovery_opportunities"])
        self.assertEqual(1, summary["recoveries"])


class BenchmarkRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_is_recorded_and_next_turn_recovers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            write_silent_wav(input_path)
            orchestrator = ScriptedOrchestrator((
                _telemetry("failed", error_type="ProviderUnavailableError"),
                _telemetry("completed", 4, 8),
            ))
            report = await run_benchmark(
                orchestrator, input_path, 2, "offline", "benchmark-session"
            )
        self.assertEqual(["failed", "completed"], [
            turn.telemetry.status for turn in report.turns
        ])
        self.assertEqual(1, report.summary()["recoveries"])

    async def test_cancellation_propagates_without_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            write_silent_wav(input_path)
            orchestrator = ScriptedOrchestrator((_telemetry("cancelled"),))
            with self.assertRaises(asyncio.CancelledError):
                await run_benchmark(orchestrator, input_path, 1, "offline")

    async def test_real_offline_turns_share_bounded_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            write_silent_wav(input_path)
            orchestrator = TurnOrchestrator(
                OfflineASRAdapter("离线输入"),
                OfflineLLMAdapter("离线回复。"),
                ToneTTSAdapter(),
                Settings(context_turns=2),
            )
            report = await run_benchmark(
                orchestrator, input_path, 5, "offline", "continuous-session"
            )
        self.assertEqual(5, report.completed_count)
        self.assertEqual(2, orchestrator.conversations.turn_count("continuous-session"))
        self.assertEqual(5, report.summary()["first_audio_ms"]["samples"])


class BenchmarkReportTests(unittest.TestCase):
    def test_atomic_report_excludes_private_runtime_fields(self):
        secret = "benchmark-secret-value"
        report = BenchmarkReport(
            profile="offline",
            character_id="march-7th",
            character_version="0.1.0",
            turns=(BenchmarkTurnRecord(1, _telemetry("completed", 3, 6)),),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "report.json"
            write_benchmark_report(output, report)
            serialized = output.read_text(encoding="utf-8")
            payload = json.loads(serialized)
            leftovers = list(root.glob(".report.json.*.tmp"))
        self.assertEqual(1, payload["report_contract_version"])
        self.assertEqual([], leftovers)
        for private in (
            secret,
            "private-session",
            "private-turn",
            "private-generation",
            "/input/path",
            "transcript",
            "reply",
            '"raw_audio"',
        ):
            self.assertNotIn(private, serialized)

    def test_report_write_failure_is_normalized_and_cleans_temporary_file(self):
        report = BenchmarkReport(
            profile="offline",
            character_id="march-7th",
            character_version="0.1.0",
            turns=(BenchmarkTurnRecord(1, _telemetry("completed", 3, 6)),),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(
                BenchmarkExecutionError, "cannot write benchmark report"
            ):
                write_benchmark_report(root, report)
            self.assertEqual([], list(root.glob(".*.tmp")))


class BenchmarkCliTests(unittest.TestCase):
    def test_offline_cli_writes_report_and_compact_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.wav"
            output_path = root / "benchmark.json"
            write_silent_wav(input_path)
            stdout = io.StringIO()
            with mock.patch.dict(
                "os.environ", {"DEEPSEEK_API_KEY": "unused-secret"}, clear=True
            ), redirect_stdout(stdout):
                exit_code = main([
                    "benchmark-turns",
                    "--profile", "offline",
                    "--turns", "3",
                    "--input", str(input_path),
                    "--output", str(output_path),
                ])
            report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(0, exit_code)
        self.assertEqual(3, report["summary"]["completed"])
        self.assertNotIn("unused-secret", json.dumps(report))
        summary = json.loads(stdout.getvalue().splitlines()[0])
        self.assertEqual("completed", summary["status"])

    def test_non_positive_turn_count_exits_two_without_report(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main([
                "benchmark-turns",
                "--turns", "0",
                "--input", "/missing.wav",
                "--output", "/missing-report.json",
            ])
        self.assertEqual(2, exit_code)
        self.assertIn("--turns", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
