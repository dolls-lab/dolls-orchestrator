"""In-memory, bounded short-term conversation context."""

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Mapping, Tuple


@dataclass(frozen=True)
class CompletedTurn:
    user: str
    assistant: str


class ConversationStore:
    def __init__(self, max_turns: int = 6) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be greater than zero")
        self.max_turns = max_turns
        self._sessions: Dict[str, Deque[CompletedTurn]] = {}

    def messages(self, session_id: str) -> List[Mapping[str, str]]:
        output: List[Mapping[str, str]] = []
        for turn in self._sessions.get(session_id, ()):
            output.append({"role": "user", "content": turn.user})
            output.append({"role": "assistant", "content": turn.assistant})
        return output

    def commit(self, session_id: str, user: str, assistant: str) -> None:
        turns = self._sessions.setdefault(
            session_id, deque(maxlen=self.max_turns)
        )
        turns.append(CompletedTurn(user=user, assistant=assistant))

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def turn_count(self, session_id: str) -> int:
        return len(self._sessions.get(session_id, ()))

