from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
import wave

from dolls_orchestrator.cli import main

from tests.helpers import write_silent_wav


class OfflineEndToEndTests(unittest.TestCase):
    def test_cli_writes_playable_wav_and_telemetry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            output_path = Path(temp_dir) / "reply.wav"
            write_silent_wav(input_path)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "run-turn",
                        "--profile",
                        "offline",
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                    ]
                )
            self.assertEqual(0, exit_code)
            self.assertTrue(output_path.is_file())
            with wave.open(str(output_path), "rb") as wav_file:
                self.assertEqual(1, wav_file.getnchannels())
                self.assertEqual(2, wav_file.getsampwidth())
                self.assertEqual(24000, wav_file.getframerate())
                self.assertGreater(wav_file.getnframes(), 0)
            lines = stdout.getvalue().splitlines()
            telemetry = json.loads(next(line for line in lines if line.startswith("{")))
            self.assertEqual("completed", telemetry["status"])
            self.assertEqual(["asr", "llm", "tts"], sorted(telemetry["stages"]))
            self.assertEqual("builtin-march-7th-style", telemetry["character_id"])
            self.assertEqual("builtin-v1", telemetry["character_version"])
            self.assertNotIn("api_key", telemetry)

    def test_invalid_input_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exit_code = main(
                [
                    "run-turn",
                    "--profile",
                    "offline",
                    "--input",
                    str(Path(temp_dir) / "missing.wav"),
                    "--output",
                    str(Path(temp_dir) / "reply.wav"),
                ]
            )
            self.assertEqual(2, exit_code)


if __name__ == "__main__":
    unittest.main()
