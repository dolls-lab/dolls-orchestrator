"""Command-line entry point for the desktop WAV-to-WAV baseline."""

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from .audio import write_wav
from .config import ConfigurationError, Settings
from .desktop_audio import AfplayPlayer, SoundDeviceRecorder
from .errors import OrchestratorError
from .interactive import InteractiveSession
from .orchestrator import TurnOrchestrator
from .profiles import build_profile


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
    devices = subparsers.add_parser("devices", help="list available audio devices")
    return parser


async def _run_turn(args: argparse.Namespace, settings: Settings) -> int:
    profile_name = args.profile or settings.profile
    profile = build_profile(profile_name, settings)
    orchestrator = TurnOrchestrator(
        asr=profile.asr,
        llm=profile.llm,
        tts=profile.tts,
        settings=settings,
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
    orchestrator = TurnOrchestrator(
        asr=profile.asr,
        llm=profile.llm,
        tts=profile.tts,
        settings=settings,
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        if getattr(args, "profile", None):
            settings = replace(settings, profile=args.profile)
        if args.command == "run-turn":
            return asyncio.run(_run_turn(args, settings))
        if args.command == "chat":
            return asyncio.run(_chat(args, settings))
        if args.command == "devices":
            print(SoundDeviceRecorder().list_devices())
            return 0
        raise ConfigurationError("unknown command")
    except (ConfigurationError, OrchestratorError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[cancelled] 用户中止", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
