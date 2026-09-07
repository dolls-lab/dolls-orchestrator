"""Text-only character evaluation fixture consumer and report runner."""

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, Mapping, Optional, Tuple

from .character import CharacterPackage
from .domain import LLMAdapter, TurnContext
from .errors import EvaluationExecutionError, EvaluationValidationError


REPORT_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    category: str
    user: str
    rubric: Tuple[str, ...]


@dataclass(frozen=True)
class EvaluationFixture:
    character_id: str
    evaluation_version: str
    language: str
    cases: Tuple[EvaluationCase, ...]


@dataclass(frozen=True)
class EvaluationCaseResult:
    case: EvaluationCase
    status: str
    reply: str
    provider: str
    model: str
    elapsed_ms: float
    usage: Mapping[str, int]
    error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.case.case_id,
            "category": self.case.category,
            "user": self.case.user,
            "rubric": list(self.case.rubric),
            "status": self.status,
            "score": None,
            "reply": self.reply,
            "provider": self.provider,
            "model": self.model,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "usage": dict(self.usage),
            "error_type": self.error_type,
        }


@dataclass(frozen=True)
class EvaluationReport:
    character: CharacterPackage
    fixture: EvaluationFixture
    profile: str
    results: Tuple[EvaluationCaseResult, ...]

    @property
    def failed_count(self) -> int:
        return sum(result.status == "failed" for result in self.results)

    @property
    def completed_count(self) -> int:
        return sum(result.status == "completed" for result in self.results)

    def summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.results),
            "completed": self.completed_count,
            "failed": self.failed_count,
            "unscored": len(self.results),
            "status": "failed" if self.failed_count else "completed",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_contract_version": REPORT_CONTRACT_VERSION,
            "character": {
                "character_id": self.character.character_id,
                "package_version": self.character.package_version,
                "language": self.character.language,
            },
            "evaluation": {
                "character_id": self.fixture.character_id,
                "evaluation_version": self.fixture.evaluation_version,
                "language": self.fixture.language,
                "case_count": len(self.fixture.cases),
            },
            "profile": self.profile,
            "summary": self.summary(),
            "cases": [result.to_dict() for result in self.results],
        }


def _required_string(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EvaluationValidationError(
            "evaluation %s.%s must be a non-empty string" % (label, key)
        )
    return item.strip()


def load_evaluation_fixture(
    path: Path, character: CharacterPackage
) -> EvaluationFixture:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvaluationValidationError("invalid evaluation fixture JSON") from exc
    if not isinstance(payload, dict):
        raise EvaluationValidationError("evaluation fixture must be an object")
    character_id = _required_string(payload, "character_id", "fixture")
    version = _required_string(payload, "evaluation_version", "fixture")
    language = _required_string(payload, "language", "fixture")
    if character_id != character.character_id:
        raise EvaluationValidationError("evaluation character does not match package")
    if language != character.language:
        raise EvaluationValidationError("evaluation language does not match package")
    values = payload.get("cases")
    if not isinstance(values, list) or not values:
        raise EvaluationValidationError("evaluation cases must be a non-empty list")
    cases = []
    identifiers = set()
    for value in values:
        if not isinstance(value, dict):
            raise EvaluationValidationError("evaluation case must be an object")
        case_id = _required_string(value, "id", "case")
        if case_id in identifiers:
            raise EvaluationValidationError("duplicate evaluation case id: %s" % case_id)
        category = _required_string(value, "category", "case")
        user = _required_string(value, "user", "case")
        rubric = value.get("rubric")
        if (
            not isinstance(rubric, list)
            or not rubric
            or any(not isinstance(item, str) or not item.strip() for item in rubric)
        ):
            raise EvaluationValidationError(
                "evaluation rubric must contain non-empty criteria"
            )
        identifiers.add(case_id)
        cases.append(EvaluationCase(
            case_id=case_id,
            category=category,
            user=user,
            rubric=tuple(item.strip() for item in rubric),
        ))
    return EvaluationFixture(
        character_id=character_id,
        evaluation_version=version,
        language=language,
        cases=tuple(cases),
    )


def _adapter_identity(adapter: LLMAdapter) -> Tuple[str, str]:
    return (
        str(getattr(adapter, "provider", "")),
        str(getattr(adapter, "model", "")),
    )


async def _run_case(
    case: EvaluationCase,
    fixture: EvaluationFixture,
    character: CharacterPackage,
    llm: LLMAdapter,
) -> EvaluationCaseResult:
    provider, model = _adapter_identity(llm)
    context = TurnContext(
        session_id="character-evaluation",
        turn_id=case.case_id,
        generation_id="%s:%s" % (fixture.evaluation_version, case.case_id),
    )
    messages = character.message_prefix()
    messages.append({"role": "user", "content": case.user})
    started = time.perf_counter()
    reply_parts = []
    usage: Mapping[str, int] = {}
    completed = False
    elapsed_ms = 0.0
    try:
        async for event in llm.stream_reply(messages, context):
            if event.kind == "text_delta":
                reply_parts.append(event.text)
            elif event.kind == "completed":
                completed = True
                provider = event.provider or provider
                model = event.model or model
                usage = {
                    str(key): int(value)
                    for key, value in event.usage.items()
                    if isinstance(value, int) and not isinstance(value, bool)
                }
                if event.elapsed_ms is not None:
                    elapsed_ms = event.elapsed_ms
        if not completed:
            raise EvaluationExecutionError("LLM stream ended without completion")
        if not elapsed_ms:
            elapsed_ms = (time.perf_counter() - started) * 1000
        return EvaluationCaseResult(
            case=case,
            status="completed",
            reply="".join(reply_parts),
            provider=provider,
            model=model,
            elapsed_ms=elapsed_ms,
            usage=usage,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return EvaluationCaseResult(
            case=case,
            status="failed",
            reply="",
            provider=provider,
            model=model,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            usage={},
            error_type=type(exc).__name__,
        )


async def run_evaluation(
    fixture: EvaluationFixture,
    character: CharacterPackage,
    llm: LLMAdapter,
    profile: str,
) -> EvaluationReport:
    results = []
    for case in fixture.cases:
        results.append(await _run_case(case, fixture, character, llm))
    return EvaluationReport(
        character=character,
        fixture=fixture,
        profile=profile,
        results=tuple(results),
    )


def write_evaluation_report(path: Path, report: EvaluationReport) -> None:
    path = Path(path)
    temporary_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=".%s." % path.name,
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
        os.replace(str(temporary_path), str(path))
    except OSError as exc:
        raise EvaluationExecutionError("cannot write evaluation report") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
