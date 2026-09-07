"""Incremental sentence segmentation for short spoken replies."""

from typing import List


class SentenceSplitter:
    TERMINATORS = set("。！？!?；;\n")

    def __init__(self, max_chars: int = 80) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be greater than zero")
        self.max_chars = max_chars
        self._buffer = ""

    def feed(self, text: str) -> List[str]:
        self._buffer += text
        sentences = []
        while self._buffer:
            boundary = self._first_boundary()
            if boundary is None and len(self._buffer) < self.max_chars:
                break
            end = boundary + 1 if boundary is not None else self._fallback_end()
            sentence = self._buffer[:end].strip()
            self._buffer = self._buffer[end:]
            if sentence:
                sentences.append(sentence)
        return sentences

    def finish(self) -> List[str]:
        remainder = self._buffer.strip()
        self._buffer = ""
        return [remainder] if remainder else []

    def _first_boundary(self):
        for index, character in enumerate(self._buffer):
            if character in self.TERMINATORS:
                return index
        return None

    def _fallback_end(self) -> int:
        window = self._buffer[: self.max_chars]
        for separator in ("，", ",", "、", " "):
            index = window.rfind(separator)
            if index >= self.max_chars // 2:
                return index + 1
        return self.max_chars

