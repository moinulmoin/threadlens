from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ThreadMessage


SENSITIVE_KEY_PARTS = (
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "auth",
    "blobencryptionkey",
    "credential",
    "key",
    "password",
    "refresh_token",
    "refreshtoken",
    "secret",
    "speculativesummarizationencryptionkey",
    "token",
)

NOISY_KEY_PARTS = (
    "allthinkingblocks",
    "assistantSuggesteddiffs".lower(),
    "diff",
    "embedding",
    "filediff",
    "gitdiff",
    "image",
    "lints",
    "originalfilestates",
)

STRUCTURAL_KEY_NAMES = {
    "id",
    "ismeta",
    "messageid",
    "parentuuid",
    "phase",
    "role",
    "sessionid",
    "type",
    "uuid",
    "version",
}


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield line_no, value


def is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", key.lower())
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def is_noisy_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", key.lower())
    return any(part in normalized for part in NOISY_KEY_PARTS)


def is_structural_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", key.lower())
    return normalized in STRUCTURAL_KEY_NAMES


def compact_text(text: str, limit: int = 12000) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def flatten_text(value: Any, *, parent_key: str = "", max_leaf: int = 6000) -> list[str]:
    if parent_key and (is_sensitive_key(parent_key) or is_noisy_key(parent_key)):
        return []

    if value is None or isinstance(value, bool | int | float):
        return []

    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return []

    if isinstance(value, str):
        text = value.strip()
        if len(text) < 2:
            return []
        return [text[:max_leaf]]

    if isinstance(value, list):
        pieces: list[str] = []
        for item in value:
            pieces.extend(flatten_text(item, parent_key=parent_key, max_leaf=max_leaf))
        return pieces

    if isinstance(value, dict):
        pieces: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            if is_structural_key(key_text) or is_sensitive_key(key_text) or is_noisy_key(key_text):
                continue
            pieces.extend(flatten_text(child, parent_key=key_text, max_leaf=max_leaf))
        return pieces

    return []


def content_to_text(content: Any) -> str:
    return compact_text("\n".join(flatten_text(content)))


TEXT_PART_TYPES = {"text", "input_text", "output_text"}


def visible_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content_to_text(content)

    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.extend(flatten_text(item))
                continue
            if not isinstance(item, dict):
                continue
            part_type = str(item.get("type") or "")
            if part_type not in TEXT_PART_TYPES:
                continue
            pieces.extend(flatten_text(item.get("text") if "text" in item else item.get("content")))
        return compact_text("\n".join(pieces))

    if isinstance(content, dict):
        part_type = str(content.get("type") or "")
        if part_type and part_type not in TEXT_PART_TYPES:
            return ""
        return content_to_text(content.get("text") if "text" in content else content.get("content"))

    return ""


def timestamp_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds = seconds / 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return str(value)
    return ""


def codex_messages(path: Path) -> Iterator[ThreadMessage]:
    thread_id = path.stem
    cwd = ""
    title = ""

    for line_no, row in read_jsonl(path):
        row_type = row.get("type", "")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}

        if row_type == "session_meta":
            thread_id = str(payload.get("id") or thread_id)
            cwd = str(payload.get("cwd") or cwd)
            title = Path(cwd).name if cwd else path.stem
            continue

        if row_type == "turn_context":
            cwd = str(payload.get("cwd") or cwd)
            if not title and cwd:
                title = Path(cwd).name
            continue

        if row_type != "response_item" or payload.get("type") != "message":
            continue

        role = str(payload.get("role") or "")
        if role not in {"user", "assistant"}:
            continue

        text = content_to_text(payload.get("content"))
        if not text:
            continue

        if not title and role == "user":
            title = text[:120]

        yield ThreadMessage(
            source="codex",
            thread_id=thread_id,
            message_id=str(payload.get("id") or f"{path.stem}:{line_no}"),
            path=path,
            line=line_no,
            timestamp=str(row.get("timestamp") or payload.get("timestamp") or ""),
            role=role,
            cwd=cwd,
            title=title or path.stem,
            text=text,
            metadata={"row_type": row_type},
        )


def claude_messages(path: Path) -> Iterator[ThreadMessage]:
    thread_id = path.stem
    cwd = ""
    title = ""

    for line_no, row in read_jsonl(path):
        if row.get("isMeta"):
            continue

        thread_id = str(row.get("sessionId") or thread_id)
        cwd = str(row.get("cwd") or cwd)
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        role = str(message.get("role") or row.get("type") or "")
        if role not in {"user", "assistant"}:
            continue

        text = content_to_text(message.get("content"))
        if not text:
            continue

        if not title and role == "user":
            title = text[:120]

        yield ThreadMessage(
            source="claude",
            thread_id=thread_id,
            message_id=str(row.get("uuid") or f"{path.stem}:{line_no}"),
            path=path,
            line=line_no,
            timestamp=str(row.get("timestamp") or ""),
            role=role,
            cwd=cwd,
            title=title or (Path(cwd).name if cwd else path.stem),
            text=text,
            metadata={
                "entrypoint": row.get("entrypoint"),
                "gitBranch": row.get("gitBranch"),
            },
        )


def agent_jsonl_messages(path: Path, *, source: str) -> Iterator[ThreadMessage]:
    thread_id = path.stem
    cwd = ""
    title = ""

    for line_no, row in read_jsonl(path):
        row_type = str(row.get("type") or "")

        if row_type in {"session", "session_start"}:
            thread_id = str(row.get("id") or thread_id)
            cwd = str(row.get("cwd") or cwd)
            title = compact_text(str(row.get("sessionTitle") or row.get("title") or ""), limit=120)
            if not title and cwd:
                title = Path(cwd).name
            continue

        if row_type != "message":
            continue

        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        role = str(message.get("role") or "")
        if role not in {"user", "assistant"}:
            continue

        text = visible_message_text(message.get("content"))
        if not text:
            continue

        if not title and role == "user":
            title = compact_text(text, limit=120)

        yield ThreadMessage(
            source=source,
            thread_id=thread_id,
            message_id=str(row.get("id") or f"{path.stem}:{line_no}"),
            path=path,
            line=line_no,
            timestamp=timestamp_text(row.get("timestamp") or message.get("timestamp")),
            role=role,
            cwd=cwd,
            title=title or (Path(cwd).name if cwd else path.stem),
            text=text,
            metadata={"row_type": row_type, "parentId": row.get("parentId")},
        )


def custom_jsonl_messages(path: Path, source: str = "custom") -> Iterator[ThreadMessage]:
    for line_no, row in read_jsonl(path):
        text = content_to_text(row)
        if not text:
            continue

        yield ThreadMessage(
            source=source,
            thread_id=str(row.get("sessionId") or row.get("thread_id") or path.stem),
            message_id=str(row.get("uuid") or row.get("id") or f"{path.stem}:{line_no}"),
            path=path,
            line=line_no,
            timestamp=str(row.get("timestamp") or row.get("created_at") or ""),
            role=str(row.get("role") or row.get("type") or "unknown"),
            cwd=str(row.get("cwd") or ""),
            title=str(row.get("title") or path.stem),
            text=text,
            metadata={},
        )
