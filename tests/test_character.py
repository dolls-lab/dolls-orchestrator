from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dolls_orchestrator.character import (
    BUILTIN_CHARACTER,
    load_character_package,
    resolve_character,
)
from dolls_orchestrator.cli import main
from dolls_orchestrator.errors import CharacterPackageError

from tests.helpers import write_character_package


class CharacterPackageTests(unittest.TestCase):
    def test_valid_package_loads_compact_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            package = load_character_package(
                write_character_package(Path(directory) / "character")
            )
            self.assertEqual("march-7th", package.character_id)
            self.assertEqual("0.1.0", package.package_version)
            self.assertEqual(1, len(package.examples))
            self.assertEqual("package", package.source)
            self.assertNotIn("system_prompt", package.summary())
            with self.assertRaises(TypeError):
                package.behavior["style"] = "changed"

    def test_missing_and_tampered_packages_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "character"
            with self.assertRaisesRegex(CharacterPackageError, "does not exist"):
                load_character_package(root)
            write_character_package(root)
            (root / "system_prompt.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(CharacterPackageError, "integrity"):
                load_character_package(root)

    def test_incompatible_and_unsafe_manifests_fail_before_entrypoint_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = write_character_package(Path(directory) / "character")
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["contract_version"] = 2
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(CharacterPackageError, "unsupported"):
                load_character_package(root)

        with tempfile.TemporaryDirectory() as directory:
            root = write_character_package(Path(directory) / "character")
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entrypoints"]["system_prompt"] = "../outside.txt"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(CharacterPackageError, "entrypoints"):
                load_character_package(root)

    def test_malformed_hashed_content_fails_shape_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = write_character_package(Path(directory) / "character")
            behavior_path = root / "behavior.json"
            behavior_path.write_text("[]\n", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib
            manifest["integrity"]["files"]["behavior.json"] = hashlib.sha256(
                behavior_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(CharacterPackageError, "behavior"):
                load_character_package(root)

    def test_no_path_uses_identified_builtin_fallback(self):
        self.assertIs(BUILTIN_CHARACTER, resolve_character(None))
        self.assertEqual("builtin", resolve_character(None).summary()["source"])


class CharacterCliTests(unittest.TestCase):
    def test_validate_and_info_emit_compact_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = write_character_package(Path(directory) / "character")
            for argv in (
                ["validate-character", str(root)],
                ["character-info", "--character-package", str(root)],
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(0, main(argv))
                value = json.loads(stdout.getvalue())
                self.assertEqual("march-7th", value["character_id"])
                self.assertEqual("package", value["source"])
                self.assertNotIn("system_prompt", value)

    def test_info_uses_environment_and_builtin_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = write_character_package(Path(directory) / "character")
            with mock.patch.dict(
                "os.environ", {"DOLLS_CHARACTER_PACKAGE_PATH": str(root)}, clear=True
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(0, main(["character-info"]))
                self.assertEqual("package", json.loads(stdout.getvalue())["source"])
            with mock.patch.dict("os.environ", {}, clear=True):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(0, main(["character-info"]))
                self.assertEqual("builtin", json.loads(stdout.getvalue())["source"])

    def test_command_line_package_overrides_environment_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment_package = write_character_package(root / "environment")
            override_package = write_character_package(root / "override")
            manifest_path = override_package / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["package_version"] = "0.2.0-test"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.dict(
                "os.environ",
                {"DOLLS_CHARACTER_PACKAGE_PATH": str(environment_package)},
                clear=True,
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(0, main([
                        "character-info", "--character-package", str(override_package)
                    ]))
            self.assertEqual("0.2.0-test", json.loads(stdout.getvalue())["package_version"])

    def test_dialogue_command_rejects_explicit_bad_package_before_turn(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = main([
                "run-turn",
                "--profile", "offline",
                "--character-package", "/missing/character",
                "--input", "/also/missing.wav",
                "--output", "/tmp/unused.wav",
            ])
        self.assertEqual(2, result)
        self.assertIn("character package directory", stderr.getvalue())
        self.assertNotIn("input WAV", stderr.getvalue())

    def test_invalid_explicit_package_exits_nonzero_without_character_content(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(2, main(["validate-character", "/missing/character"]))
        self.assertIn("does not exist", stderr.getvalue())
        self.assertNotIn("你是", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
