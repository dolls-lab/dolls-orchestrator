"""Interactive half-duplex desktop conversation loop."""

import asyncio
import json
from pathlib import Path
import tempfile
from typing import Awaitable, Callable, Optional

from .audio import write_wav
from .desktop_audio import Player, Recorder
from .errors import OrchestratorError
from .orchestrator import TurnOrchestrator


Prompt = Callable[[str], Awaitable[str]]
Output = Callable[[str], None]


async def console_prompt(text: str) -> str:
    return await asyncio.to_thread(input, text)


class InteractiveSession:
    def __init__(
        self,
        orchestrator: TurnOrchestrator,
        recorder: Recorder,
        player: Optional[Player],
        prompt: Prompt = console_prompt,
        output: Output = print,
        session_id: str = "desktop-interactive",
    ) -> None:
        self.orchestrator = orchestrator
        self.recorder = recorder
        self.player = player
        self.prompt = prompt
        self.output = output
        self.session_id = session_id
        self.orchestrator.set_state_sink(self._orchestrator_state)

    async def run(self, max_turns: Optional[int] = None) -> int:
        completed = 0
        self.output("[idle] 按 Enter 开始录音；输入 q 退出")
        while max_turns is None or completed < max_turns:
            command = (await self.prompt("> ")).strip().lower()
            if command in {"q", "quit", "exit"}:
                self.output("[completed] 会话已退出")
                break
            if command:
                self.output("[idle] 未识别命令；按 Enter 录音，输入 q 退出")
                continue
            try:
                with tempfile.TemporaryDirectory(prefix="dolls-chat-") as temp_dir:
                    input_path = Path(temp_dir) / "input.wav"
                    reply_path = Path(temp_dir) / "reply.wav"
                    self.output("[listening] 正在录音，按 Enter 停止")
                    stop_signal = self.prompt("")
                    await self.recorder.record_until(input_path, stop_signal)
                    result = await self.orchestrator.run_turn(
                        input_path, session_id=self.session_id
                    )
                    write_wav(reply_path, result.audio, result.audio_format)
                    self.output("ASR: %s" % result.transcript)
                    self.output("Reply: %s" % result.reply_text)
                    self.output(
                        json.dumps(
                            result.telemetry.to_dict(), ensure_ascii=False, sort_keys=True
                        )
                    )
                    if self.player is not None:
                        self.output("[playing] 正在播放")
                        await self.player.play(reply_path)
                    self.output("[completed] 本轮完成")
                    completed += 1
            except OrchestratorError as exc:
                self.output("[recoverable_error] %s" % exc)
            self.output("[idle] 按 Enter 开始录音；输入 q 退出")
        return completed

    def _orchestrator_state(self, state: str) -> None:
        if state in {"transcribing", "generating", "synthesizing", "cancelled", "failed"}:
            self.output("[%s]" % state)
