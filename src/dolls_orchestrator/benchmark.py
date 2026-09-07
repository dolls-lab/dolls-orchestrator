"""Sequential voice-turn reliability and latency benchmark."""

import asyncio
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, Optional, Tuple

from .audio import inspect_wav
from .errors import (
    BenchmarkExecutionError,
    BenchmarkValidationError,
    OrchestratorError,
    TurnCancelledError,
)
from .orchestrator import TurnOrchestrator
from .domain import TurnTelemetry


BENCHMARK_REPORT_CONTRACT_VERSION = 1


def _rounded(value: Optional[float]) -> Optional[float]:
    return round(value, 3) if value is not None else None


def percentile_summary(values: Iterable[float]) -> Dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"samples": 0, "p50": None, "p95": None}

    def nearest_rank(percent: float) -> float:
        index = max(0, math.ceil(percent * len(ordered)) - 1)
        return round(ordered[index], 3)

    return {
        "samples": len(ordered),
        "p50": nearest_rank(0.50),
        "p95": nearest_rank(0.95),
    }


@dataclass(frozen=True)
class BenchmarkTurnRecord:
    index: int
    telemetry: TurnTelemetry

    def to_dict(self) -> Dict[str, Any]:
        stages = {}
        for name, stage in self.telemetry.stages.items():
            stages[name] = {
                "provider": stage.provider,
                "model": stage.model,
                "elapsed_ms": round(stage.elapsed_ms, 3),
                "first_output_ms": _rounded(stage.first_output_ms),
            }
        return {
            "index": self.index,
            "status": self.telemetry.status,
            "first_audio_ms": _rounded(self.telemetry.first_audio_ms),
            "total_ms": round(self.telemetry.total_ms, 3),
            "stages": stages,
            "error_stage": self.telemetry.error_stage,
            "error_type": self.telemetry.error_type,
        }


@dataclass(frozen=True)
class BenchmarkReport:
    profile: str
    character_id: str
    character_version: str
    turns: Tuple[BenchmarkTurnRecord, ...]

    @property
    def failed_count(self) -> int:
        return sum(turn.telemetry.status == "failed" for turn in self.turns)

    @property
    def completed_count(self) -> int:
        return sum(turn.telemetry.status == "completed" for turn in self.turns)

    def summary(self) -> Dict[str, Any]:
        total = len(self.turns)
        opportunities = 0
        recoveries = 0
        for current, following in zip(self.turns, self.turns[1:]):
            if current.telemetry.status == "failed":
                opportunities += 1
                if following.telemetry.status == "completed":
                    recoveries += 1
        successful = [
            turn.telemetry
            for turn in self.turns
            if turn.telemetry.status == "completed"
        ]
        return {
            "status": "failed" if self.failed_count else "completed",
            "total": total,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "success_rate": round(self.completed_count / total, 6) if total else 0.0,
            "first_audio_ms": percentile_summary(
                telemetry.first_audio_ms
                for telemetry in successful
                if telemetry.first_audio_ms is not None
            ),
            "total_ms": percentile_summary(
                telemetry.total_ms for telemetry in successful
            ),
            "recovery_opportunities": opportunities,
            "recoveries": recoveries,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_contract_version": BENCHMARK_REPORT_CONTRACT_VERSION,
            "profile": self.profile,
            "character": {
                "character_id": self.character_id,
                "package_version": self.character_version,
            },
            "summary": self.summary(),
            "turns": [turn.to_dict() for turn in self.turns],
        }


async def run_benchmark(
    orchestrator: TurnOrchestrator,
    input_path: Path,
    turn_count: int,
    profile: str,
    session_id: str = "reliability-benchmark",
) -> BenchmarkReport:
    if (
        not isinstance(turn_count, int)
        or isinstance(turn_count, bool)
        or turn_count <= 0
    ):
        raise BenchmarkValidationError("benchmark turn count must be greater than zero")
    if not isinstance(session_id, str) or not session_id.strip():
        raise BenchmarkValidationError("benchmark session ID must not be empty")
    inspect_wav(Path(input_path))

    records = []
    for index in range(1, turn_count + 1):
        try:
            result = await orchestrator.run_turn(
                Path(input_path), session_id=session_id.strip()
            )
            telemetry = result.telemetry
        except TurnCancelledError as exc:
            raise asyncio.CancelledError() from exc
        except OrchestratorError:
            telemetry = orchestrator.last_telemetry
            if telemetry is None:
                raise BenchmarkExecutionError(
                    "benchmark turn failed without telemetry"
                )
        records.append(BenchmarkTurnRecord(index=index, telemetry=telemetry))

    return BenchmarkReport(
        profile=profile,
        character_id=orchestrator.character.character_id,
        character_version=orchestrator.character.package_version,
        turns=tuple(records),
    )


def write_benchmark_report(path: Path, report: BenchmarkReport) -> None:
    destination = Path(path)
    temporary_path = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(destination.parent),
            prefix=".%s." % destination.name,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(
                report.to_dict(),
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(destination))
    except OSError as exc:
        raise BenchmarkExecutionError("cannot write benchmark report") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
