"""Command-line entry point for the desktop WAV-to-WAV baseline."""

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from .audio import write_wav
from .character import load_character_package, resolve_character
from .config import ConfigurationError, Settings
from .desktop_audio import AfplayPlayer, SoundDeviceRecorder
from .evaluation import (
    load_evaluation_fixture,
    run_evaluation,
    write_evaluation_report,
)
from .errors import OrchestratorError
from .health import check_service_health
from .interactive import InteractiveSession
from .orchestrator import TurnOrchestrator
from .profiles import build_profile
from .terminal_service import TerminalServiceNotReadyError, run_terminal_service


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dolls-orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_turn = subparsers.add_parser("run-turn", help="run one desktop WAV-to-WAV turn")
    run_turn.add_argument("--input", required=True, type=Path, help="input WAV path")
    run_turn.add_argument("--output", required=True, type=Path, help="output WAV path")
    run_turn.add_argument(
        "--profile",
        choices=("offline", "offline-macos", "local-no-api", "local-voice"),
        help="adapter profile; overrides DOLLS_PROFILE",
    )
    run_turn.add_argument("--session-id", default="desktop")
    run_turn.add_argument(
        "--character-package", type=Path, help="contract-v1 character package directory"
    )
    chat = subparsers.add_parser("chat", help="start an interactive push-to-talk session")
    chat.add_argument(
        "--profile",
        choices=("offline", "offline-macos", "local-no-api", "local-voice"),
        default="local-no-api",
    )
    chat.add_argument("--session-id", default="desktop-interactive")
    chat.add_argument("--device", help="sounddevice input device index or name")
    chat.add_argument("--no-playback", action="store_true")
    chat.add_argument("--max-turns", type=int, help="stop after this many successful turns")
    chat.add_argument(
        "--character-package", type=Path, help="contract-v1 character package directory"
    )
    devices = subparsers.add_parser("devices", help="list available audio devices")
    validate_character = subparsers.add_parser(
        "validate-character", help="validate one character package"
    )
    validate_character.add_argument("package", type=Path)
    character_info = subparsers.add_parser(
        "character-info", help="show active character metadata"
    )
    character_info.add_argument("--character-package", type=Path)
    evaluate = subparsers.add_parser(
        "evaluate-character", help="run a text-only character evaluation fixture"
    )
    evaluate.add_argument("--character-package", required=True, type=Path)
    evaluate.add_argument("--evaluations", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    evaluate.add_argument(
        "--profile",
        choices=("offline", "local-voice"),
        default="offline",
        help="LLM profile; local-voice retains DeepSeek network and key guards",
    )
    health = subparsers.add_parser(
        "health", help="check character and adapter readiness without external I/O"
    )
    health.add_argument(
        "--profile",
        choices=("offline", "offline-macos", "local-no-api", "local-voice"),
        help="adapter profile; overrides DOLLS_PROFILE",
    )
    health.add_argument("--character-package", type=Path)
    health.add_argument(
        "--terminal",
        action="store_true",
        help="include terminal transport, codec, and authentication readiness",
    )
    terminal = subparsers.add_parser(
        "serve-terminal", help="serve terminal WebSocket voice turns"
    )
    terminal.add_argument(
        "--profile",
        choices=("offline", "offline-macos", "local-no-api", "local-voice"),
        help="adapter profile; overrides DOLLS_PROFILE",
    )
    terminal.add_argument("--host", help="bind host; overrides DOLLS_TERMINAL_HOST")
    terminal.add_argument(
        "--port", type=int, help="bind port; overrides DOLLS_TERMINAL_PORT"
    )
    terminal.add_argument(
        "--allow-lan",
        action="store_true",
        help="explicitly allow a non-loopback bind address",
    )
    terminal.add_argument("--character-package", type=Path)
    return parser


async def _run_turn(args: argparse.Namespace, settings: Settings) -> int:
    profile_name = args.profile or settings.profile
    profile = build_profile(profile_name, settings)
    character = resolve_character(settings.character_package_path)
    orchestrator = TurnOrchestrator(
        asr=profile.asr,
        llm=profile.llm,
        tts=profile.tts,
        settings=settings,
        character=character,
    )
    result = await orchestrator.run_turn(args.input, session_id=args.session_id)
    write_wav(args.output, result.audio, result.audio_format)
    print("ASR: %s" % result.transcript)
    print("Reply: %s" % result.reply_text)
    print(json.dumps(result.telemetry.to_dict(), ensure_ascii=False, sort_keys=True))
    print("Audio: %s" % args.output)
    return 0


def _device_value(value):
    if value is None:
        return None
    return int(value) if value.isdigit() else value


async def _chat(args: argparse.Namespace, settings: Settings) -> int:
    if args.max_turns is not None and args.max_turns <= 0:
        raise ConfigurationError("--max-turns must be greater than zero")
    profile = build_profile(args.profile, settings)
    character = resolve_character(settings.character_package_path)
    orchestrator = TurnOrchestrator(
        asr=profile.asr,
        llm=profile.llm,
        tts=profile.tts,
        settings=settings,
        character=character,
    )
    recorder = SoundDeviceRecorder(device=_device_value(args.device))
    player = None if args.no_playback else AfplayPlayer()
    session = InteractiveSession(
        orchestrator=orchestrator,
        recorder=recorder,
        player=player,
        session_id=args.session_id,
    )
    await session.run(max_turns=args.max_turns)
    return 0


async def _evaluate_character(args: argparse.Namespace, settings: Settings) -> int:
    character = load_character_package(args.character_package)
    fixture = load_evaluation_fixture(args.evaluations, character)
    profile = build_profile(args.profile, settings)
    report = await run_evaluation(fixture, character, profile.llm, args.profile)
    write_evaluation_report(args.output, report)
    print(json.dumps(report.summary(), ensure_ascii=False, sort_keys=True))
    print("Report: %s" % args.output)
    return 1 if report.failed_count else 0


async def _serve_terminal(args: argparse.Namespace, settings: Settings) -> int:
    def started(running):
        print(json.dumps(running.status(), ensure_ascii=False, sort_keys=True))

    try:
        await run_terminal_service(
            settings,
            profile_name=args.profile or settings.profile,
            host=args.host or settings.terminal_host,
            port=settings.terminal_port if args.port is None else args.port,
            allow_lan=args.allow_lan,
            on_started=started,
        )
    except TerminalServiceNotReadyError as exc:
        print(json.dumps(exc.report.to_dict(), ensure_ascii=False, sort_keys=True))
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        if getattr(args, "profile", None):
            settings = replace(settings, profile=args.profile)
        if getattr(args, "character_package", None) is not None:
            settings = replace(
                settings, character_package_path=args.character_package.expanduser()
            )
        if args.command == "run-turn":
            return asyncio.run(_run_turn(args, settings))
        if args.command == "chat":
            return asyncio.run(_chat(args, settings))
        if args.command == "devices":
            print(SoundDeviceRecorder().list_devices())
            return 0
        if args.command == "validate-character":
            print(json.dumps(
                load_character_package(args.package).summary(),
                ensure_ascii=False,
                sort_keys=True,
            ))
            return 0
        if args.command == "character-info":
            print(json.dumps(
                resolve_character(settings.character_package_path).summary(),
                ensure_ascii=False,
                sort_keys=True,
            ))
            return 0
        if args.command == "evaluate-character":
            return asyncio.run(_evaluate_character(args, settings))
        if args.command == "health":
            report = check_service_health(
                args.profile or settings.profile,
                settings,
                include_terminal=args.terminal,
            )
            print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if report.ready else 1
        if args.command == "serve-terminal":
            return asyncio.run(_serve_terminal(args, settings))
        raise ConfigurationError("unknown command")
    except (ConfigurationError, OrchestratorError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[cancelled] 用户中止", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
