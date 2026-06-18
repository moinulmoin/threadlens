from __future__ import annotations

import glob
import json
import os
import sqlite3
import urllib.parse
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from .extract import (
    amp_history_messages,
    agent_jsonl_messages,
    claude_messages,
    codex_messages,
    compact_text,
    content_to_text,
    custom_jsonl_messages,
    read_jsonl,
    timestamp_text,
    visible_message_text,
)
from .models import ThreadMessage
from .profiles import SourceProfile


DEFAULT_SOURCE_NAMES = ("codex", "claude", "cursor", "pi", "omp", "amp", "droid", "opencode")
SOURCE_NAMES = ("codex", "claude", "cursor", "pi", "omp", "amp", "droid", "opencode")


def _dedup_paths(paths: list[Path]) -> list[Path]:
    """Drop duplicate paths while preserving order."""
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _xdg_config_home(home: Path, env: Mapping[str, str]) -> Path:
    root = env.get("XDG_CONFIG_HOME")
    return Path(root) if root else home / ".config"


def _xdg_data_home(home: Path, env: Mapping[str, str]) -> Path:
    root = env.get("XDG_DATA_HOME")
    return Path(root) if root else home / ".local" / "share"


def _appdata_roots(home: Path, env: Mapping[str, str]) -> list[Path]:
    """Windows AppData roots (Roaming, Local), honoring env vars when present.

    The exact Windows store paths for some agents are unverified — see the
    cross-platform note in README and the tracking GitHub issue.
    """
    roaming = env.get("APPDATA")
    local = env.get("LOCALAPPDATA")
    # Env-provided roots are *additional* candidates, never replacements: some
    # agents ignore APPDATA/LOCALAPPDATA and still write to the conventional
    # AppData/Roaming and AppData/Local locations, so always include both.
    roots: list[Path] = []
    if roaming:
        roots.append(Path(roaming))
    roots.append(home / "AppData" / "Roaming")
    if local:
        roots.append(Path(local))
    roots.append(home / "AppData" / "Local")
    return _dedup_paths(roots)


def source_paths(
    source: str,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    home = home or Path.home()
    env = environ if environ is not None else os.environ
    if source == "codex":
        return sorted((home / ".codex" / "sessions").glob("**/*.jsonl"))
    if source == "claude":
        paths = sorted((home / ".claude" / "projects").glob("**/*.jsonl"))
        history = home / ".claude" / "history.jsonl"
        if history.exists():
            paths.append(history)
        return paths
    if source == "cursor":
        # Cursor (a VS Code fork) stores its User dir per OS. XDG/AppData paths are
        # *additional* candidates, never replacements — some apps ignore the env vars
        # and still write to the conventional location, so always include it too.
        user_dirs = _dedup_paths([
            home / "Library" / "Application Support" / "Cursor" / "User",  # macOS
            _xdg_config_home(home, env) / "Cursor" / "User",  # Linux ($XDG_CONFIG_HOME)
            home / ".config" / "Cursor" / "User",  # Linux conventional fallback
            *[r / "Cursor" / "User" for r in _appdata_roots(home, env)],  # Windows
        ])
        paths: list[Path] = []
        for root in user_dirs:
            if not root.exists():
                continue
            global_state = root / "globalStorage" / "state.vscdb"
            if global_state.exists():
                paths.append(global_state)
            workspace = root / "workspaceStorage"
            if workspace.exists():
                paths.extend(sorted(workspace.glob("**/state.vscdb")))
        return paths
    if source == "pi":
        return sorted((home / ".pi" / "agent" / "sessions").glob("**/*.jsonl"))
    if source == "omp":
        return sorted((home / ".omp" / "agent" / "sessions").glob("**/*.jsonl"))
    if source == "amp":
        amp_dirs = _dedup_paths([
            _xdg_data_home(home, env) / "amp",  # $XDG_DATA_HOME
            home / ".local" / "share" / "amp",  # conventional fallback
            *[r / "amp" for r in _appdata_roots(home, env)],  # Windows (best-effort)
        ])
        histories: list[Path] = []
        for amp_dir in amp_dirs:
            history = amp_dir / "history.jsonl"
            if history.exists():
                histories.append(history)
        return _dedup_paths(histories)
    if source == "droid":
        return sorted((home / ".factory" / "sessions").glob("**/*.jsonl"))
    if source == "opencode":
        opencode_dirs = _dedup_paths([
            _xdg_data_home(home, env) / "opencode",  # $XDG_DATA_HOME
            home / ".local" / "share" / "opencode",  # conventional fallback
            *[r / "opencode" for r in _appdata_roots(home, env)],  # Windows (best-effort)
        ])
        dbs: list[Path] = []
        for oc_dir in opencode_dirs:
            db = oc_dir / "opencode.db"
            if db.exists() and opencode_db_has_messages(db):
                dbs.append(db)
        return _dedup_paths(dbs)
    raise ValueError(f"Unknown source: {source}")


def describe_sources(home: Path | None = None) -> list[tuple[str, int, list[Path]]]:
    rows = []
    for source in SOURCE_NAMES:
        paths = source_paths(source, home=home)
        rows.append((source, len(paths), paths[:5]))
    return rows


def iter_messages(source: str, *, home: Path | None = None, limit_files: int | None = None) -> Iterator[ThreadMessage]:
    paths = source_paths(source, home=home)
    if limit_files is not None:
        paths = paths[:limit_files]

    for path in paths:
        yield from iter_path_messages(source, path)


def iter_path_messages(source: str, path: Path) -> Iterator[ThreadMessage]:
    if source == "codex":
        yield from codex_messages(path)
    elif source == "claude":
        yield from claude_messages(path)
    elif source == "cursor":
        yield from cursor_messages(path)
    elif source in {"pi", "omp", "droid"}:
        yield from agent_jsonl_messages(path, source=source)
    elif source == "amp":
        yield from amp_history_messages(path)
    elif source == "opencode":
        yield from opencode_messages(path)


def iter_custom_messages(paths: list[Path]) -> Iterator[ThreadMessage]:
    for path in custom_jsonl_paths(paths):
        yield from custom_jsonl_messages(path)


def custom_jsonl_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        expanded = root.expanduser()
        if expanded.is_dir():
            files.extend(sorted(expanded.glob("**/*.jsonl")))
        elif expanded.is_file():
            files.append(expanded)
    return files


def source_profile_paths(profile: SourceProfile) -> list[Path]:
    files: list[Path] = []
    for pattern in profile.paths:
        expanded = Path(pattern).expanduser()
        if expanded.is_dir():
            files.extend(sorted(expanded.glob("**/*.jsonl")))
            continue
        if expanded.is_file():
            files.append(expanded)
            continue
        if glob.has_magic(str(expanded)):
            files.extend(sorted(Path(match) for match in glob.glob(str(expanded), recursive=True) if Path(match).is_file()))
    return sorted(dict.fromkeys(files))


def source_profile_messages(profile: SourceProfile, path: Path) -> Iterator[ThreadMessage]:
    if profile.format != "jsonl":
        return

    for line_no, row in read_jsonl(path):
        text_value = value_at_path(row, profile.text_key)
        text = content_to_text(text_value if text_value is not None else row)
        if not text:
            continue

        session_id = scalar_text(value_at_path(row, profile.session_key)) or path.stem
        message_id = scalar_text(value_at_path(row, profile.message_key)) or f"{path.stem}:{line_no}"
        role = scalar_text(value_at_path(row, profile.role_key)) or scalar_text(row.get("role")) or "unknown"
        timestamp = scalar_text(value_at_path(row, profile.timestamp_key))
        cwd = scalar_text(value_at_path(row, profile.cwd_key))
        title = scalar_text(value_at_path(row, profile.title_key)) or text[:120] or path.stem

        yield ThreadMessage(
            source=profile.name,
            thread_id=session_id,
            message_id=message_id,
            path=path,
            line=line_no,
            timestamp=timestamp,
            role=role,
            cwd=cwd,
            title=compact_text(title, limit=120),
            text=compact_text(text),
            metadata={"profile": profile.name},
        )


def value_at_path(value: Any, key_path: str) -> Any:
    if not key_path:
        return None

    current = value
    for part in key_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    return content_to_text(value)


def connect_sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri_path = urllib.parse.quote(str(path), safe="/:")
    return sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)


def decode_sqlite_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def cursor_messages(path: Path) -> Iterator[ThreadMessage]:
    try:
        conn = connect_sqlite_readonly(path)
    except sqlite3.Error:
        return

    try:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type = 'table'")
        }
    except sqlite3.Error:
        return

    try:
        if "cursorDiskKV" not in tables and "ItemTable" not in tables:
            return

        if "cursorDiskKV" in tables:
            yield from cursor_disk_kv_messages(path, conn)
        if "ItemTable" in tables:
            yield from cursor_item_table_messages(path, conn)
    except sqlite3.Error:
        return
    finally:
        conn.close()


def cursor_disk_kv_messages(path: Path, conn: sqlite3.Connection) -> Iterator[ThreadMessage]:
    query = """
        select key, value
        from cursorDiskKV
        where key like 'composerData:%'
           or key like 'bubbleId:%'
    """
    try:
        rows = conn.execute(query)
    except sqlite3.Error:
        return

    for row_no, (key, raw_value) in enumerate(rows, 1):
        value = decode_sqlite_value(raw_value)
        if value is None:
            continue
        text = cursor_message_text(value, key=str(key))
        if not text:
            continue

        if key.startswith("bubbleId:"):
            parts = key.split(":")
            thread_id = parts[1] if len(parts) > 1 else key
            message_id = parts[-1]
        elif key.startswith("composerData:"):
            thread_id = key.removeprefix("composerData:")
            message_id = thread_id
        else:
            thread_id = extract_cursor_thread_id(value) or key
            message_id = key

        role = extract_cursor_role(value)
        timestamp = extract_cursor_timestamp(value)
        cwd = extract_cursor_cwd(value)
        title = extract_cursor_title(value, fallback=thread_id)

        yield ThreadMessage(
            source="cursor",
            thread_id=str(thread_id),
            message_id=str(message_id),
            path=path,
            line=row_no,
            timestamp=timestamp,
            role=role,
            cwd=cwd,
            title=title,
            text=compact_text(text),
            metadata={"cursor_key": key},
        )


def cursor_item_table_messages(path: Path, conn: sqlite3.Connection) -> Iterator[ThreadMessage]:
    query = """
        select key, value
        from ItemTable
        where key like 'composer.%'
           or key like 'composerData:%'
           or key like 'conversation%'
           or key like 'cursor.composer%'
    """
    try:
        rows = conn.execute(query)
    except sqlite3.Error:
        return

    for row_no, (key, raw_value) in enumerate(rows, 1):
        value = decode_sqlite_value(raw_value)
        if value is None:
            continue
        text = cursor_message_text(value, key=str(key))
        if not text:
            continue

        yield ThreadMessage(
            source="cursor",
            thread_id=extract_cursor_thread_id(value) or str(key),
            message_id=str(key),
            path=path,
            line=row_no,
            timestamp=extract_cursor_timestamp(value),
            role=extract_cursor_role(value),
            cwd=extract_cursor_cwd(value),
            title=extract_cursor_title(value, fallback=str(key)),
            text=compact_text(text),
            metadata={"cursor_key": key, "table": "ItemTable"},
        )


def cursor_message_text(value: Any, *, key: str) -> str:
    if not isinstance(value, dict):
        return ""

    if key.startswith("agentKv:blob:"):
        return ""

    if key.startswith("bubbleId:"):
        return first_cursor_text(value, ("text", "richText", "content"))

    if key.startswith("composerData:") or key.startswith("composer."):
        return first_cursor_text(value, ("text", "richText", "name", "title"))

    if key.startswith("conversation") or key.startswith("cursor.composer"):
        return first_cursor_text(value, ("text", "richText", "content", "name", "title"))

    return ""


def first_cursor_text(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = cursor_value_to_text(value.get(key))
        if text:
            return text
    return ""


def cursor_value_to_text(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                pass
            else:
                return content_to_text(decoded)
        return content_to_text(value)
    return content_to_text(value)


def extract_cursor_thread_id(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("composerId", "conversationId", "sessionId", "id"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return ""


def extract_cursor_role(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("role", "type"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return "cursor"


def extract_cursor_timestamp(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("createdAt", "timestamp", "lastUpdatedAt", "updatedAt"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
            if isinstance(candidate, int | float):
                return str(candidate)
    return ""


def extract_cursor_cwd(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    repos = value.get("trackedGitRepos") or value.get("workspaceUris") or value.get("workspaceFolders")
    if isinstance(repos, list) and repos:
        first = repos[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("path", "uri", "fsPath"):
                candidate = first.get(key)
                if isinstance(candidate, str):
                    return candidate
    return ""


def extract_cursor_title(value: Any, *, fallback: str) -> str:
    if isinstance(value, dict):
        for key in ("text", "richText", "name", "title"):
            candidate = cursor_value_to_text(value.get(key))
            if candidate:
                return compact_text(candidate, limit=120)
    return fallback


def opencode_db_has_messages(path: Path) -> bool:
    try:
        conn = connect_sqlite_readonly(path)
    except sqlite3.Error:
        return True
    try:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type = 'table'")
        }
        if "part" in tables:
            row = conn.execute("select count(*) from part").fetchone()
            return bool(row and int(row[0]) > 0)
        if "message" in tables:
            row = conn.execute("select count(*) from message").fetchone()
            return bool(row and int(row[0]) > 0)
        return False
    except sqlite3.Error:
        return True
    finally:
        conn.close()


def opencode_messages(path: Path) -> Iterator[ThreadMessage]:
    try:
        conn = connect_sqlite_readonly(path)
    except sqlite3.Error:
        return

    try:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type = 'table'")
        }
    except sqlite3.Error:
        conn.close()
        return

    try:
        if {"session", "message", "part"}.issubset(tables):
            yield from opencode_part_messages(path, conn)
        elif {"session", "message"}.issubset(tables):
            yield from opencode_message_rows(path, conn)
    except sqlite3.Error:
        return
    finally:
        conn.close()


def opencode_part_messages(path: Path, conn: sqlite3.Connection) -> Iterator[ThreadMessage]:
    query = """
        select
            p.id as part_id,
            p.message_id as message_id,
            p.session_id as session_id,
            p.time_created as part_time_created,
            p.data as part_data,
            m.data as message_data,
            s.directory as directory,
            s.path as session_path,
            s.title as title
        from part p
        left join message m on m.id = p.message_id
        left join session s on s.id = p.session_id
        order by p.time_created, p.id
    """
    for row_no, row in enumerate(conn.execute(query), 1):
        (
            part_id,
            message_id,
            session_id,
            part_time_created,
            raw_part_data,
            raw_message_data,
            directory,
            session_path,
            title,
        ) = row
        part_data = decode_sqlite_value(raw_part_data)
        message_data = decode_sqlite_value(raw_message_data)
        text = opencode_part_text(part_data)
        if not text:
            continue
        role = opencode_role(message_data, part_data)
        if role not in {"user", "assistant"}:
            continue

        yield ThreadMessage(
            source="opencode",
            thread_id=str(session_id),
            message_id=str(part_id or message_id or f"{session_id}:{row_no}"),
            path=path,
            line=row_no,
            timestamp=timestamp_text(part_time_created),
            role=role,
            cwd=str(directory or session_path or ""),
            title=compact_text(str(title or session_id), limit=120),
            text=text,
            metadata={"message_id": message_id},
        )


def opencode_message_rows(path: Path, conn: sqlite3.Connection) -> Iterator[ThreadMessage]:
    query = """
        select
            m.id as message_id,
            m.session_id as session_id,
            m.time_created as time_created,
            m.data as message_data,
            s.directory as directory,
            s.path as session_path,
            s.title as title
        from message m
        left join session s on s.id = m.session_id
        order by m.time_created, m.id
    """
    for row_no, row in enumerate(conn.execute(query), 1):
        message_id, session_id, time_created, raw_message_data, directory, session_path, title = row
        message_data = decode_sqlite_value(raw_message_data)
        role = opencode_role(message_data, None)
        if role not in {"user", "assistant"}:
            continue
        text = opencode_part_text(message_data)
        if not text:
            continue

        yield ThreadMessage(
            source="opencode",
            thread_id=str(session_id),
            message_id=str(message_id or f"{session_id}:{row_no}"),
            path=path,
            line=row_no,
            timestamp=timestamp_text(time_created),
            role=role,
            cwd=str(directory or session_path or ""),
            title=compact_text(str(title or session_id), limit=120),
            text=text,
            metadata={},
        )


def opencode_role(message_data: Any, part_data: Any) -> str:
    for value in (message_data, part_data):
        if isinstance(value, dict):
            for key in ("role", "author", "type"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate in {"user", "assistant"}:
                    return candidate
    return ""


def opencode_part_text(value: Any) -> str:
    if isinstance(value, str):
        return content_to_text(value)
    if not isinstance(value, dict):
        return ""

    part_type = str(value.get("type") or "")
    if part_type in {"tool", "tool_call", "tool_result", "step-start", "step-finish", "snapshot"}:
        return ""
    if part_type:
        return visible_message_text(value)

    for key in ("text", "content", "message"):
        text = visible_message_text(value.get(key))
        if text:
            return text
    return ""
