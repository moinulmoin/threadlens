from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import ThreadMessage
from .paths import ensure_private_storage_path


SCHEMA = """
create table if not exists messages (
    id integer primary key,
    doc_key text not null unique,
    source text not null,
    thread_id text not null,
    message_id text not null,
    path text not null,
    line integer not null,
    timestamp text not null,
    role text not null,
    cwd text not null,
    title text not null,
    text text not null,
    metadata_json text not null
);

create table if not exists indexed_files (
    source text not null,
    path text not null,
    mtime_ns integer not null,
    size integer not null,
    message_count integer not null,
    indexed_at text not null default current_timestamp,
    primary key (source, path)
);

create virtual table if not exists messages_fts using fts5(
    text,
    title,
    cwd,
    source,
    role,
    content='messages',
    content_rowid='id'
);
"""


class ThreadStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_private_storage_path(self.db_path)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        ensure_private_storage_path(self.db_path)

    def close(self) -> None:
        self.conn.close()

    def reset(self) -> None:
        self.conn.execute("delete from messages")
        self.conn.execute("delete from indexed_files")
        self.rebuild_fts()
        self.conn.commit()

    def delete_sources(self, sources: list[str]) -> None:
        if not sources:
            return
        placeholders = ",".join("?" for _ in sources)
        self.conn.execute(f"delete from messages where source in ({placeholders})", sources)
        self.conn.execute(f"delete from indexed_files where source in ({placeholders})", sources)
        self.rebuild_fts()
        self.conn.commit()

    def delete_file(self, source: str, path: Path) -> None:
        self.conn.execute(
            "delete from messages where source = ? and path = ?",
            (source, str(path)),
        )
        self.conn.execute(
            "delete from indexed_files where source = ? and path = ?",
            (source, str(path)),
        )

    def file_is_current(self, source: str, path: Path, *, mtime_ns: int, size: int) -> bool:
        row = self.conn.execute(
            """
            select 1
            from indexed_files
            where source = ? and path = ? and mtime_ns = ? and size = ?
            """,
            (source, str(path), mtime_ns, size),
        ).fetchone()
        return row is not None

    def mark_file_indexed(self, source: str, path: Path, *, mtime_ns: int, size: int, message_count: int) -> None:
        self.conn.execute(
            """
            insert or replace into indexed_files (
                source, path, mtime_ns, size, message_count, indexed_at
            )
            values (?, ?, ?, ?, ?, current_timestamp)
            """,
            (source, str(path), mtime_ns, size, message_count),
        )

    def add_messages(self, messages: list[ThreadMessage], *, rebuild: bool = True, commit: bool = True) -> int:
        if not messages:
            return 0
        rows = [
            (
                message.doc_key,
                message.source,
                message.thread_id,
                message.message_id,
                str(message.path),
                message.line,
                message.timestamp,
                message.role,
                message.cwd,
                message.title,
                message.text,
                json.dumps(message.metadata, sort_keys=True),
            )
            for message in messages
        ]
        self.conn.executemany(
            """
            insert or replace into messages (
                doc_key, source, thread_id, message_id, path, line, timestamp,
                role, cwd, title, text, metadata_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if rebuild:
            self.rebuild_fts()
        if commit:
            self.conn.commit()
        return len(rows)

    def rebuild_fts(self) -> None:
        self.conn.execute("insert into messages_fts(messages_fts) values('rebuild')")

    def stats(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                select source, count(*) as messages, count(distinct thread_id) as threads
                from messages
                group by source
                order by source
                """
            )
        )

    def message_count(self, source: str | None = None) -> int:
        if source:
            row = self.conn.execute(
                "select count(*) as messages from messages where source = ?",
                (source,),
            ).fetchone()
        else:
            row = self.conn.execute("select count(*) as messages from messages").fetchone()
        return int(row["messages"] if row else 0)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        source: str | None = None,
        raw_fts: bool = False,
    ) -> list[sqlite3.Row]:
        fts_query = query if raw_fts else make_fts_query(query)
        if not fts_query:
            return []

        params: list[Any] = [fts_query]
        where = "messages_fts match ?"
        if source:
            where += " and messages.source = ?"
            params.append(source)
        params.append(limit)

        sql = f"""
            select
                messages.*,
                snippet(messages_fts, 0, '[', ']', '...', 28) as snippet,
                bm25(messages_fts) as rank
            from messages_fts
            join messages on messages_fts.rowid = messages.id
            where {where}
            order by rank, timestamp desc
            limit ?
        """
        return list(self.conn.execute(sql, params))

    def search_sessions(
        self,
        query: str,
        *,
        limit: int = 10,
        source: str | None = None,
        cwd_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        tokens = tokenize_query(query)
        if not tokens or limit <= 0:
            return []

        candidates: list[dict[str, Any]] = []
        row_limit = max(100, limit * 30)

        stages = [
            (make_fts_query_from_tokens(tokens, operator="AND", prefix=False), "exact", 100.0),
            (make_fts_query_from_tokens(tokens, operator="AND", prefix=True), "prefix", 80.0),
            (make_fts_query_from_tokens(tokens, operator="OR", prefix=False), "any", 55.0),
        ]

        sessions: list[dict[str, Any]] = []
        for fts_query, stage, base_score in stages:
            if not fts_query:
                continue
            candidates.extend(
                self._search_message_candidates(
                    fts_query,
                    tokens,
                    source=source,
                    cwd_prefix=cwd_prefix,
                    stage=stage,
                    base_score=base_score,
                    limit=row_limit,
                )
            )
            sessions = sorted_sessions(candidates, tokens=tokens)
            if stage == "any" and sessions:
                return sessions[:limit]
            if not sessions_need_fallback(sessions, tokens, limit):
                return sessions[:limit]

        if not sessions:
            candidates.extend(
                self._fuzzy_message_candidates(
                    tokens,
                    source=source,
                    cwd_prefix=cwd_prefix,
                    limit=row_limit,
                )
            )
        return sorted_sessions(candidates, tokens=tokens)[:limit]

    def _search_message_candidates(
        self,
        fts_query: str,
        tokens: list[str],
        *,
        source: str | None,
        cwd_prefix: str | None,
        stage: str,
        base_score: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [fts_query]
        where = "messages_fts match ?"
        if source:
            where += " and messages.source = ?"
            params.append(source)
        if cwd_prefix:
            where += " and (messages.cwd = ? or messages.cwd like ?)"
            params.extend([cwd_prefix, f"{cwd_prefix.rstrip('/')}/%"])
        params.append(limit)

        sql = f"""
            select
                messages.*,
                snippet(messages_fts, 0, '[', ']', '...', 32) as snippet,
                bm25(messages_fts) as rank
            from messages_fts
            join messages on messages_fts.rowid = messages.id
            where {where}
            order by rank, timestamp desc
            limit ?
        """
        rows = self.conn.execute(sql, params)

        candidates = []
        for row in rows:
            row_dict = dict(row)
            rank = float(row_dict.get("rank") or 0)
            text_for_matching = " ".join(
                [
                    row_dict.get("title") or "",
                    row_dict.get("cwd") or "",
                    row_dict.get("text") or "",
                ]
            )
            matched_terms = match_terms(tokens, text_for_matching, fuzzy=False)
            score = (
                base_score
                + min(25.0, max(0.0, -rank * 5.0))
                + recency_boost(row_dict.get("timestamp") or "")
                + project_boost(tokens, row_dict)
                + ordered_span_boost(tokens, text_for_matching)
            )
            candidates.append(
                {
                    "row": row_dict,
                    "snippet": row_dict.get("snippet") or make_plain_snippet(row_dict.get("text") or "", tokens),
                    "score": score,
                    "stage": stage,
                    "matched_terms": matched_terms,
                }
            )
        return candidates

    def _fuzzy_message_candidates(
        self,
        tokens: list[str],
        *,
        source: str | None,
        cwd_prefix: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        params: list[Any] = []
        where = ""
        if source:
            where = "where source = ?"
            params.append(source)
        if cwd_prefix:
            clause = "(cwd = ? or cwd like ?)"
            if where:
                where += f" and {clause}"
            else:
                where = f"where {clause}"
            params.extend([cwd_prefix, f"{cwd_prefix.rstrip('/')}/%"])
        sql = f"""
            select *
            from messages
            {where}
            order by timestamp desc
        """
        candidates: list[dict[str, Any]] = []
        rows = self.conn.execute(sql, params)

        for row in rows:
            row_dict = dict(row)
            text_for_matching = " ".join(
                [
                    row_dict.get("title") or "",
                    row_dict.get("cwd") or "",
                    row_dict.get("text") or "",
                ]
            )
            matched_terms = match_terms(tokens, text_for_matching, fuzzy=True)
            if not matched_terms:
                continue
            ratio = len(matched_terms) / max(1, len(tokens))
            if ratio < 0.5:
                continue
            score = (
                35.0
                + (ratio * 20.0)
                + recency_boost(row_dict.get("timestamp") or "")
                + project_boost(tokens, row_dict)
                + ordered_span_boost(tokens, text_for_matching)
            )
            candidates.append(
                {
                    "row": row_dict,
                    "snippet": make_plain_snippet(row_dict.get("text") or "", tokens),
                    "score": score,
                    "stage": "fuzzy",
                    "matched_terms": matched_terms,
                }
            )
            if len(candidates) >= limit:
                break
        return candidates

    def get_session(self, source: str, thread_id: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                select *
                from messages
                where source = ? and thread_id = ?
                order by timestamp, id
                """,
                (source, thread_id),
            )
        )

    def find_sessions(self, thread_id: str, source: str | None = None) -> list[sqlite3.Row]:
        params: list[Any] = [thread_id]
        where = "thread_id = ?"
        if source:
            where += " and source = ?"
            params.append(source)
        return list(
            self.conn.execute(
                f"""
                select source, thread_id, max(timestamp) as last_timestamp, max(cwd) as cwd, max(title) as title, count(*) as messages
                from messages
                where {where}
                group by source, thread_id
                order by last_timestamp desc
                """,
                params,
            )
        )


def make_fts_query(query: str) -> str:
    tokens = tokenize_query(query)
    return make_fts_query_from_tokens(tokens, operator="AND", prefix=False)


def tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+", query.lower(), flags=re.UNICODE)
    safe_tokens = [token for token in tokens if token.strip() and (len(token) > 1 or not token.isdigit())]
    return safe_tokens


def make_fts_query_from_tokens(tokens: list[str], *, operator: str, prefix: bool) -> str:
    safe_tokens = []
    for token in tokens:
        if not re.fullmatch(r"[A-Za-z0-9_]+", token):
            continue
        if prefix and len(token) >= 2:
            safe_tokens.append(f"{token}*")
        else:
            safe_tokens.append(token)
    return f" {operator} ".join(safe_tokens)


def group_candidate_sessions(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    seen_messages: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        row = candidate["row"]
        key = (row["source"], row["thread_id"])
        message_key = (row["source"], row["thread_id"], row["message_id"])
        if message_key in seen_messages:
            continue
        seen_messages.add(message_key)

        result = grouped.setdefault(
            key,
            {
                "result_id": f"{row['source']}:{row['thread_id']}",
                "source": row["source"],
                "session_id": row["thread_id"],
                "thread_id": row["thread_id"],
                "cwd": row["cwd"],
                "title": row["title"],
                "last_timestamp": row["timestamp"],
                "score": 0.0,
                "matched_terms": set(),
                "best_snippets": [],
                "source_path": row["path"],
                "source_line": row["line"],
                "actions": {},
                "_message_count": 0,
                "_best_score": 0.0,
            },
        )
        result["_message_count"] += 1
        result["_best_score"] = max(result["_best_score"], candidate["score"])
        result["matched_terms"].update(candidate.get("matched_terms") or [])
        if row["timestamp"] > result["last_timestamp"]:
            result["last_timestamp"] = row["timestamp"]
        if not result["cwd"] and row["cwd"]:
            result["cwd"] = row["cwd"]
        if not result["title"] and row["title"]:
            result["title"] = row["title"]
        result["best_snippets"].append(
            {
                "message_id": row["message_id"],
                "timestamp": row["timestamp"],
                "role": row["role"],
                "snippet": candidate["snippet"],
                "source_path": row["path"],
                "source_line": row["line"],
                "match_type": candidate["stage"],
                "score": round(candidate["score"], 4),
            }
        )

    results = []
    for result in grouped.values():
        result["matched_terms"] = sorted(result["matched_terms"])
        result["best_snippets"] = sorted(result["best_snippets"], key=lambda item: item["score"], reverse=True)[:3]
        message_boost = min(5.0, result["_message_count"] * 0.35)
        term_boost = len(result["matched_terms"]) * 12.0
        result["score"] = round(float(result["_best_score"] + message_boost + term_boost), 4)
        result.pop("_message_count", None)
        result.pop("_best_score", None)
        results.append(result)
    return results


def sorted_sessions(candidates: list[dict[str, Any]], *, tokens: list[str] | None = None) -> list[dict[str, Any]]:
    sessions = group_candidate_sessions(candidates)
    if tokens:
        sessions.sort(key=lambda result: (token_coverage(result), result["score"]), reverse=True)
    else:
        sessions.sort(key=lambda result: result["score"], reverse=True)
    return sessions


def sessions_need_fallback(sessions: list[dict[str, Any]], tokens: list[str], limit: int) -> bool:
    if not sessions:
        return True
    if len(sessions) < limit:
        return True
    required_coverage = len(set(tokens))
    if required_coverage == 0:
        return False
    return all(token_coverage(result) < required_coverage for result in sessions[:limit])


def token_coverage(result: dict[str, Any]) -> int:
    return len(set(result.get("matched_terms") or []))


def match_terms(tokens: list[str], text: str, *, fuzzy: bool) -> list[str]:
    text_lower = text.lower()
    words = set(re.findall(r"[A-Za-z0-9_]+", text_lower))
    matched = []
    for token in tokens:
        if token in text_lower or any(word.startswith(token) for word in words):
            matched.append(token)
            continue
        if fuzzy and fuzzy_contains(token, words):
            matched.append(token)
    return matched


def fuzzy_contains(token: str, words: set[str]) -> bool:
    if len(token) < 3:
        return False
    max_distance = 1 if len(token) <= 4 else 2
    for word in words:
        if not word or word[0] != token[0]:
            continue
        if abs(len(word) - len(token)) > max_distance:
            continue
        if bounded_levenshtein(token, word, max_distance) <= max_distance:
            return True
    return False


def bounded_levenshtein(left: str, right: str, max_distance: int) -> int:
    previous_previous: list[int] | None = None
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, 1):
        current = [i]
        row_min = i
        for j, right_char in enumerate(right, 1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (left_char != right_char)
            value = min(insert, delete, replace)
            if (
                previous_previous is not None
                and i > 1
                and j > 1
                and left[i - 1] == right[j - 2]
                and left[i - 2] == right[j - 1]
            ):
                value = min(value, previous_previous[j - 2] + 1)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous_previous = previous
        previous = current
    return previous[-1]


def recency_boost(timestamp: str) -> float:
    if not timestamp:
        return 0.0
    normalized = timestamp.replace("Z", "+00:00")
    try:
        parsed = time.mktime(time.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return 0.0
    age_days = max(0.0, (time.time() - parsed) / 86400)
    return max(0.0, 8.0 - (age_days / 14.0))


def project_boost(tokens: list[str], row: dict[str, Any]) -> float:
    haystack = f"{row.get('title') or ''} {row.get('cwd') or ''}".lower()
    if not haystack:
        return 0.0
    matched = sum(1 for token in tokens if token in haystack)
    return min(12.0, matched * 4.0)


def ordered_span_boost(tokens: list[str], text: str) -> float:
    if len(tokens) < 2:
        return 0.0

    words = re.findall(r"[A-Za-z0-9_]+", text.lower())
    if not words:
        return 0.0

    positions: list[int] = []
    start = 0
    for token in tokens:
        for index in range(start, len(words)):
            if words[index] == token or words[index].startswith(token):
                positions.append(index)
                start = index + 1
                break
        else:
            return 0.0

    span = positions[-1] - positions[0] + 1
    slack = span - len(tokens)
    if slack <= 2:
        return 18.0
    if slack <= 6:
        return 12.0
    if slack <= 12:
        return 6.0
    return 0.0


def make_plain_snippet(text: str, tokens: list[str], *, radius: int = 90) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    lowered = compact.lower()
    positions = [lowered.find(token) for token in tokens if lowered.find(token) >= 0]
    if not positions:
        return compact[: radius * 2]
    start = max(0, min(positions) - radius)
    end = min(len(compact), min(positions) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return prefix + compact[start:end] + suffix
