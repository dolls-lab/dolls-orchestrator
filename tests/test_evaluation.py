import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dolls_orchestrator.character import load_character_package
from dolls_orchestrator.cli import main
from dolls_orchestrator.domain import LLMEvent
from dolls_orchestrator.errors import EvaluationValidationError
from dolls_orchestrator.evaluation import (
    load_evaluation_fixture,
    run_evaluation,
    write_evaluation_report,
)

from tests.helpers import write_character_package, write_evaluation_fixture


class RecordingLLM:
    provider = "recording"
    model = "recording-v1"

    def __init__(self, fail_case=None):
        self.fail_case = fail_case
        self.calls = []

    async def stream_reply(self, messages, context):
        self.calls.append((list(messages), context))
        if context.turn_id == self.fail_case:
            raise RuntimeError("secret-key-must-not-enter-report")
        yield LLMEvent(kind="text_delta", text="回答：")
        yield LLMEvent(kind="text_delta", text=messages[-1]["content"])
        yield LLMEvent(
            kind="completed",
            provider=self.provider,
            model=self.model,
            usage={"input_messages": len(messages), "output_tokens": 3},
            elapsed_ms=12.5,
        )


class EvaluationFixtureTests(unittest.TestCase):
    def test_valid_fixture_loads_immutable_ordered_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character = load_character_package(write_character_package(root / "package"))
            fixture = load_evaluation_fixture(
                write_evaluation_fixture(root / "evaluation.json"), character
            )
            self.assertEqual("0.1.0", fixture.evaluation_version)
            self.assertEqual(["case-identity", "case-style"], [
                case.case_id for case in fixture.cases
            ])
            self.assertIsInstance(fixture.cases[0].rubric, tuple)

    def test_invalid_json_duplicate_and_package_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character = load_character_package(write_character_package(root / "package"))
            invalid = root / "invalid.json"
            invalid.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(EvaluationValidationError, "invalid"):
                load_evaluation_fixture(invalid, character)

            cases = [{
                "id": "duplicate",
                "category": "identity",
                "user": "问题",
                "rubric": ["标准"],
            }] * 2
            duplicate = write_evaluation_fixture(root / "duplicate.json", cases=cases)
            with self.assertRaisesRegex(EvaluationValidationError, "duplicate"):
                load_evaluation_fixture(duplicate, character)

            mismatch = write_evaluation_fixture(
                root / "mismatch.json", character_id="another-character"
            )
            with self.assertRaisesRegex(EvaluationValidationError, "does not match"):
                load_evaluation_fixture(mismatch, character)

    def test_empty_rubric_and_language_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character = load_character_package(write_character_package(root / "package"))
            cases = [{
                "id": "case",
                "category": "identity",
                "user": "问题",
                "rubric": [],
            }]
            path = write_evaluation_fixture(root / "rubric.json", cases=cases)
            with self.assertRaisesRegex(EvaluationValidationError, "rubric"):
                load_evaluation_fixture(path, character)
            path = write_evaluation_fixture(root / "language.json", language="en-US")
            with self.assertRaisesRegex(EvaluationValidationError, "language"):
                load_evaluation_fixture(path, character)


class EvaluationRunnerTests(unittest.TestCase):
    def _inputs(self, root):
        character = load_character_package(write_character_package(root / "package"))
        fixture = load_evaluation_fixture(
            write_evaluation_fixture(root / "evaluation.json"), character
        )
        return character, fixture

    def test_cases_are_isolated_and_report_is_unscored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character, fixture = self._inputs(root)
            adapter = RecordingLLM()
            report = asyncio.run(run_evaluation(
                fixture, character, adapter, profile="test"
            ))
            self.assertEqual({
                "total": 2,
                "completed": 2,
                "failed": 0,
                "unscored": 2,
                "status": "completed",
            }, report.summary())
            self.assertEqual(2, len(adapter.calls))
            for index, (messages, context) in enumerate(adapter.calls):
                self.assertEqual(4, len(messages))
                self.assertEqual(fixture.cases[index].user, messages[-1]["content"])
                self.assertEqual(fixture.cases[index].case_id, context.turn_id)
            self.assertNotIn(fixture.cases[0].user, [
                message["content"] for message in adapter.calls[1][0]
            ])
            self.assertIsNone(report.to_dict()["cases"][0]["score"])

    def test_case_failure_is_isolated_and_secret_message_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character, fixture = self._inputs(root)
            adapter = RecordingLLM(fail_case="case-identity")
            report = asyncio.run(run_evaluation(
                fixture, character, adapter, profile="test"
            ))
            self.assertEqual(1, report.failed_count)
            self.assertEqual(1, report.completed_count)
            self.assertEqual("RuntimeError", report.results[0].error_type)
            serialized = json.dumps(report.to_dict(), ensure_ascii=False)
            self.assertNotIn("secret-key", serialized)

    def test_report_write_is_stable_and_excludes_package_prompt_and_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character, fixture = self._inputs(root)
            report = asyncio.run(run_evaluation(
                fixture, character, RecordingLLM(), profile="test"
            ))
            output = root / "nested" / "report.json"
            write_evaluation_report(output, report)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(1, payload["report_contract_version"])
            self.assertEqual("march-7th", payload["character"]["character_id"])
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("你是测试三月七", serialized)
            self.assertNotIn("示例问题", serialized)


class EvaluationCliTests(unittest.TestCase):
    def _argv(self, root, profile="offline"):
        return [
            "evaluate-character",
            "--character-package", str(root / "package"),
            "--evaluations", str(root / "evaluation.json"),
            "--output", str(root / "report.json"),
            "--profile", profile,
        ]

    def test_offline_cli_writes_success_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_character_package(root / "package")
            write_evaluation_fixture(root / "evaluation.json")
            stdout = io.StringIO()
            with mock.patch.dict("os.environ", {}, clear=True), redirect_stdout(stdout):
                self.assertEqual(0, main(self._argv(root)))
            payload = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(2, payload["summary"]["completed"])
            self.assertEqual("offline", payload["profile"])
            self.assertIn('"failed": 0', stdout.getvalue())

    def test_invalid_fixture_exits_two_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_character_package(root / "package")
            write_evaluation_fixture(
                root / "evaluation.json", character_id="wrong-character"
            )
            stderr = io.StringIO()
            with mock.patch.dict("os.environ", {}, clear=True), redirect_stderr(stderr):
                self.assertEqual(2, main(self._argv(root)))
            self.assertFalse((root / "report.json").exists())
            self.assertIn("does not match", stderr.getvalue())

    def test_guarded_deepseek_writes_failed_diagnostic_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_character_package(root / "package")
            write_evaluation_fixture(root / "evaluation.json")
            with mock.patch.dict("os.environ", {}, clear=True), redirect_stdout(io.StringIO()):
                self.assertEqual(1, main(self._argv(root, profile="local-voice")))
            payload = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(2, payload["summary"]["failed"])
            self.assertEqual(
                "ProviderConfigurationError", payload["cases"][0]["error_type"]
            )
            self.assertNotIn("DEEPSEEK_API_KEY", json.dumps(payload))

    def test_unwritable_report_path_exits_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_character_package(root / "package")
            write_evaluation_fixture(root / "evaluation.json")
            blocked_parent = root / "not-a-directory"
            blocked_parent.write_text("file", encoding="utf-8")
            argv = self._argv(root)
            argv[argv.index(str(root / "report.json"))] = str(blocked_parent / "report.json")
            stderr = io.StringIO()
            with mock.patch.dict("os.environ", {}, clear=True), redirect_stderr(stderr):
                self.assertEqual(2, main(argv))
            self.assertIn("cannot write evaluation report", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
