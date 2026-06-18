from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ThreadMessage:
    source: str
    thread_id: str
    message_id: str
    path: Path
    line: int
    timestamp: str
    role: str
    cwd: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def doc_key(self) -> str:
        return f"{self.source}:{self.path}:{self.message_id}:{self.line}"

