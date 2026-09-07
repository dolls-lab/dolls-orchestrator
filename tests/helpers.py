import hashlib
import json
from pathlib import Path
import wave


def write_silent_wav(path: Path, duration_ms: int = 100, sample_rate: int = 16000) -> None:
    frame_count = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0\0" * frame_count)


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_character_package(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "system_prompt.txt").write_text("你是测试三月七。\n", encoding="utf-8")
    _json(root / "behavior.json", {
        "emotion_tags": ["cheerful", "gentle"],
        "reply_max_chars": 120,
        "unknown_strategy": "不知道时坦率说明。",
    })
    _json(root / "examples.json", [
        {"user": "示例问题", "assistant": "示例回答"}
    ])
    _json(root / "sources.json", {
        "claims": [{
            "claim_id": "test-claim",
            "summary": "合成测试主张",
            "evidence": [{"evidence_id": "test-evidence", "content_sha256": "0" * 64}],
        }],
        "source_type": "hksr-postgres",
    })
    entrypoints = {
        "behavior": "behavior.json",
        "examples": "examples.json",
        "sources": "sources.json",
        "system_prompt": "system_prompt.txt",
    }
    _json(root / "manifest.json", {
        "character_id": "march-7th",
        "compatibility": {"orchestrator_contract": 1},
        "contract_version": 1,
        "display_name": "三月七",
        "entrypoints": entrypoints,
        "integrity": {
            "algorithm": "sha256",
            "files": {name: _sha256(root / name) for name in entrypoints.values()},
        },
        "language": "zh-CN",
        "package_version": "0.1.0",
    })
    return root


def write_evaluation_fixture(path: Path, cases=None, **overrides) -> Path:
    if cases is None:
        cases = [
            {
                "id": "case-identity",
                "category": "identity",
                "user": "请介绍一下自己。",
                "rubric": ["身份信息准确", "表达自然"],
            },
            {
                "id": "case-style",
                "category": "casual-style",
                "user": "下午做些什么？",
                "rubric": ["语气轻快", "回复简短"],
            },
        ]
    payload = {
        "character_id": "march-7th",
        "evaluation_version": "0.1.0",
        "language": "zh-CN",
        "cases": cases,
    }
    payload.update(overrides)
    _json(path, payload)
    return path
