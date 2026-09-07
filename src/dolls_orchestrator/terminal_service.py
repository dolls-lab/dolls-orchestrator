"""Assembly and lifecycle for the runnable terminal voice service."""

import asyncio
from dataclasses import dataclass
import ipaddress
import signal
from typing import Callable, Optional

from .character import resolve_character
from .config import Settings
from .errors import TerminalServiceError
from .health import ServiceHealthReport, check_service_health
from .opus_codec import LibOpusCodec
from .orchestrator import TurnOrchestrator
from .profiles import build_profile
from .terminal_bridge import OrchestratorTerminalBridge
from .terminal_transport import serve_terminal


class TerminalServiceNotReadyError(TerminalServiceError):
    def __init__(self, report: ServiceHealthReport) -> None:
        super().__init__("terminal service readiness is blocked")
        self.report = report


@dataclass(frozen=True)
class RunningTerminalService:
    server: object
    profile: str
    host: str
    port: int

    def status(self):
        return {
            "status": "listening",
            "profile": self.profile,
            "host": self.host,
            "port": self.port,
        }

    async def close(self) -> None:
        self.server.close()
        await self.server.wait_closed()


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_bind_policy(host: str, allow_lan: bool) -> None:
    if not isinstance(host, str) or not host.strip():
        raise TerminalServiceError("terminal host is invalid")
    if not _is_loopback(host.strip()) and not allow_lan:
        raise TerminalServiceError("terminal LAN binding requires explicit opt-in")


async def start_terminal_service(
    settings: Settings,
    profile_name: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    allow_lan: bool = False,
    server_factory=serve_terminal,
) -> RunningTerminalService:
    selected_profile = profile_name or settings.profile
    selected_host = (host or settings.terminal_host).strip()
    selected_port = settings.terminal_port if port is None else port
    if not isinstance(selected_port, int) or not 0 <= selected_port <= 65535:
        raise TerminalServiceError("terminal port is invalid")
    validate_bind_policy(selected_host, allow_lan)

    health = check_service_health(selected_profile, settings, include_terminal=True)
    if not health.ready:
        raise TerminalServiceNotReadyError(health)

    profile = build_profile(selected_profile, settings)
    character = resolve_character(settings.character_package_path)
    orchestrator = TurnOrchestrator(
        asr=profile.asr,
        llm=profile.llm,
        tts=profile.tts,
        settings=settings,
        character=character,
    )
    codec = LibOpusCodec(
        str(settings.libopus_path) if settings.libopus_path is not None else None
    )
    handler = OrchestratorTerminalBridge(orchestrator, codec)
    server = await server_factory(
        handler,
        settings.terminal_token,
        host=selected_host,
        port=selected_port,
    )
    actual_port = selected_port
    sockets = getattr(server, "sockets", None)
    if selected_port == 0 and sockets:
        actual_port = sockets[0].getsockname()[1]
    return RunningTerminalService(
        server=server,
        profile=selected_profile,
        host=selected_host,
        port=actual_port,
    )


async def run_terminal_service(
    settings: Settings,
    profile_name: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    allow_lan: bool = False,
    shutdown_event: Optional[asyncio.Event] = None,
    on_started: Optional[Callable[[RunningTerminalService], None]] = None,
    server_factory=serve_terminal,
) -> None:
    running = await start_terminal_service(
        settings,
        profile_name=profile_name,
        host=host,
        port=port,
        allow_lan=allow_lan,
        server_factory=server_factory,
    )
    stop = shutdown_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    registered = []
    if shutdown_event is None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signum, stop.set)
            except (NotImplementedError, RuntimeError):
                continue
            registered.append(signum)
    try:
        if on_started is not None:
            on_started(running)
        await stop.wait()
    finally:
        for signum in registered:
            loop.remove_signal_handler(signum)
        await running.close()
