"""Independent reader for the public character-package contract."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from .errors import CharacterPackageError


CONTRACT_VERSION = 1
SUPPORTED_LANGUAGE = "zh-CN"
REQUIRED_ENTRYPOINTS = {
    "system_prompt": "system_prompt.txt",
    "behavior": "behavior.json",
    "examples": "examples.json",
    "sources": "sources.json",
}
BUILTIN_INSTRUCTION = (
    "你是三月七风格的对话角色。语气活泼、友善、简短；不知道时坦率说明，"
    "不要声称自己是真实人物。单次回答尽量控制在一百五十个汉字以内。"
)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class CharacterExample:
    user: str
    assistant: str


@dataclass(frozen=True)
class CharacterPackage:
    character_id: str
    display_name: str
    package_version: str
    language: str
    system_prompt: str
    behavior: Mapping[str, Any]
    examples: Tuple[CharacterExample, ...]
    source_type: str
    claim_count: int
    source: str

    def message_prefix(self):
        messages = [{"role": "system", "content": self.system_prompt}]
        for example in self.examples:
            messages.append({"role": "user", "content": example.user})
            messages.append({"role": "assistant", "content": example.assistant})
        return messages

    def summary(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "claim_count": self.claim_count,
            "display_name": self.display_name,
            "example_count": len(self.examples),
            "language": self.language,
            "package_version": self.package_version,
            "source": self.source,
            "source_type": self.source_type,
        }


BUILTIN_CHARACTER = CharacterPackage(
    character_id="builtin-march-7th-style",
    display_name="三月七风格（内置回退）",
    package_version="builtin-v1",
    language=SUPPORTED_LANGUAGE,
    system_prompt=BUILTIN_INSTRUCTION,
    behavior=MappingProxyType({"reply_max_chars": 150}),
    examples=(),
    source_type="builtin",
    claim_count=0,
    source="builtin",
)


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CharacterPackageError("invalid character %s JSON" % label) from error


def _string(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise CharacterPackageError(
            "character %s.%s must be a non-empty string" % (label, key)
        )
    return item.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
    except OSError as error:
        raise CharacterPackageError("cannot read character file: %s" % path.name) from error
    return digest.hexdigest()


def load_character_package(root: Path) -> CharacterPackage:
    root = Path(root)
    if not root.is_dir():
        raise CharacterPackageError("character package directory does not exist")
    manifest = _load_json(root / "manifest.json", "manifest")
    if not isinstance(manifest, dict):
        raise CharacterPackageError("character manifest must be an object")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise CharacterPackageError("unsupported character package contract version")
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, dict) or compatibility.get("orchestrator_contract") != 1:
        raise CharacterPackageError("unsupported character orchestrator compatibility")
    entrypoints = manifest.get("entrypoints")
    if entrypoints != REQUIRED_ENTRYPOINTS:
        raise CharacterPackageError("unsafe or unsupported character entrypoints")
    for filename in entrypoints.values():
        candidate = Path(filename)
        if candidate.is_absolute() or ".." in candidate.parts or candidate.name != filename:
            raise CharacterPackageError("unsafe character entrypoint path")

    integrity = manifest.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        raise CharacterPackageError("character integrity algorithm must be sha256")
    hashes = integrity.get("files")
    if not isinstance(hashes, dict) or set(hashes) != set(REQUIRED_ENTRYPOINTS.values()):
        raise CharacterPackageError("character integrity file set is incomplete")
    for filename in REQUIRED_ENTRYPOINTS.values():
        expected = hashes.get(filename)
        if not isinstance(expected, str) or len(expected) != 64:
            raise CharacterPackageError("invalid character checksum: %s" % filename)
        path = root / filename
        if not path.is_file():
            raise CharacterPackageError("missing character file: %s" % filename)
        if _sha256(path) != expected:
            raise CharacterPackageError("character integrity check failed: %s" % filename)

    character_id = _string(manifest, "character_id", "manifest")
    display_name = _string(manifest, "display_name", "manifest")
    package_version = _string(manifest, "package_version", "manifest")
    language = _string(manifest, "language", "manifest")
    if language != SUPPORTED_LANGUAGE:
        raise CharacterPackageError("unsupported character package language")
    try:
        prompt = (root / entrypoints["system_prompt"]).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise CharacterPackageError("cannot read character system prompt") from error
    if not prompt:
        raise CharacterPackageError("character system prompt must not be empty")

    behavior = _load_json(root / entrypoints["behavior"], "behavior")
    if not isinstance(behavior, dict):
        raise CharacterPackageError("character behavior must be an object")
    reply_max = behavior.get("reply_max_chars")
    if not isinstance(reply_max, int) or isinstance(reply_max, bool) or not 1 <= reply_max <= 500:
        raise CharacterPackageError("character reply_max_chars must be between 1 and 500")
    unknown_strategy = behavior.get("unknown_strategy")
    if not isinstance(unknown_strategy, str) or not unknown_strategy.strip():
        raise CharacterPackageError("character unknown_strategy must not be empty")
    emotion_tags = behavior.get("emotion_tags")
    if (
        not isinstance(emotion_tags, list)
        or any(not isinstance(item, str) or not item.strip() for item in emotion_tags)
        or len(set(emotion_tags)) != len(emotion_tags)
    ):
        raise CharacterPackageError("character emotion_tags must be unique strings")

    example_values = _load_json(root / entrypoints["examples"], "examples")
    if not isinstance(example_values, list) or not example_values:
        raise CharacterPackageError("character examples must be a non-empty list")
    examples = []
    for value in example_values:
        if not isinstance(value, dict):
            raise CharacterPackageError("character example must be an object")
        examples.append(CharacterExample(
            user=_string(value, "user", "example"),
            assistant=_string(value, "assistant", "example"),
        ))

    sources = _load_json(root / entrypoints["sources"], "sources")
    if not isinstance(sources, dict):
        raise CharacterPackageError("character sources must be an object")
    source_type = _string(sources, "source_type", "sources")
    claims = sources.get("claims")
    if not isinstance(claims, list) or not claims:
        raise CharacterPackageError("character source claims must be a non-empty list")
    serialized = json.dumps(sources, ensure_ascii=False).lower()
    if "postgresql://" in serialized or "postgres://" in serialized:
        raise CharacterPackageError("character sources contain a database credential")
    for claim in claims:
        if not isinstance(claim, dict):
            raise CharacterPackageError("character source claim must be an object")
        _string(claim, "claim_id", "claim")
        _string(claim, "summary", "claim")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise CharacterPackageError("character claim evidence must be a non-empty list")
        if any(not isinstance(item, dict) or "text" in item for item in evidence):
            raise CharacterPackageError("character evidence must contain compact provenance")

    return CharacterPackage(
        character_id=character_id,
        display_name=display_name,
        package_version=package_version,
        language=language,
        system_prompt=prompt,
        behavior=_freeze(behavior),
        examples=tuple(examples),
        source_type=source_type,
        claim_count=len(claims),
        source="package",
    )


def resolve_character(path: Optional[Path]) -> CharacterPackage:
    return BUILTIN_CHARACTER if path is None else load_character_package(path)
