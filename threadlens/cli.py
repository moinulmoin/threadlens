from __future__ import annotations

import argparse
import json
import shlex
import sqlite3
import string
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from . import __version__
from .models import ThreadMessage
from .paths import default_db_path
from .profiles import DEFAULT_CONFIG, ProfileConfigError, SourceProfile, load_profiles, save_profiles, validate_source_name
from .sources import (
    DEFAULT_SOURCE_NAMES,
    SOURCE_NAMES,
    custom_jsonl_paths,
    describe_sources,
    iter_path_messages,
    source_profile_messages,
    source_profile_paths,
    source_paths,
)
from .extract import custom_jsonl_messages
from .store import ThreadStore


DEFAULT_DB = default_db_path()
RESUME_TEMPLATE_FIELDS = {"cwd", "session_id", "source"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="threadlens")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite index path")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Custom source profile config")
    sub = parser.add_subparsers(dest="command", required=True)

    sources_parser = sub.add_parser("sources", help="Show detected local sources")
    sources_parser.add_argument("--home", type=Path, default=Path.home())
    sources_parser.add_argument("--json", action="store_true", help="Emit JSON")
    sources_sub = sources_parser.add_subparsers(dest="sources_command")

    sources_add = sources_sub.add_parser("add", help="Add or update a custom source profile")
    sources_add.add_argument("name")
    sources_add.add_argument("--path", action="append", required=True, help="File, directory, or glob to scan")
    sources_add.add_argument("--format", choices=("jsonl",), default="jsonl")
    sources_add.add_argument("--session-key", default="sessionId")
    sources_add.add_argument("--message-key", default="uuid")
    sources_add.add_argument("--role-key", default="message.role")
    sources_add.add_argument("--text-key", default="message.content")
    sources_add.add_argument("--timestamp-key", default="timestamp")
    sources_add.add_argument("--cwd-key", default="cwd")
    sources_add.add_argument("--title-key", default="title")
    sources_add.add_argument("--resume-template", default="")

    sources_remove = sources_sub.add_parser("remove", help="Remove a custom source profile")
    sources_remove.add_argument("name")

    refresh_parser = sub.add_parser("refresh", help="Refresh the local searchable session cache")
    add_refresh_args(refresh_parser)

    start_parser = sub.add_parser("start", help="Set up or repair the local search index")
    add_refresh_args(start_parser)

    index_parser = sub.add_parser("index", help="Alias for refresh")
    add_refresh_args(index_parser)

    search_parser = sub.add_parser("search", help="Search indexed sessions")
    search_parser.add_argument("query", nargs="+")
    search_parser.add_argument("--source", help="Restrict to one source")
    search_parser.add_argument("--cwd", "--project", dest="cwd", help="Restrict to sessions from this cwd/project directory")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true", help="Emit JSON lines")
    search_parser.add_argument("--no-bootstrap", action="store_true", help="Do not auto-index when the search index is empty")
    search_parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)

    doctor_parser = sub.add_parser("doctor", help="Check source stores and adapter readability")
    doctor_parser.add_argument("--home", type=Path, default=Path.home())
    doctor_parser.add_argument("--json", action="store_true", help="Emit JSON")

    brief_parser = sub.add_parser("brief", help="Print a compact session brief")
    brief_parser.add_argument("result_id", help="Result id, usually source:session_id")
    brief_parser.add_argument("--source", help="Source when passing a bare session id")
    brief_parser.add_argument("--json", action="store_true", help="Emit JSON")

    resume_parser = sub.add_parser("resume", help="Print the verified resume command for a result")
    resume_parser.add_argument("result_id", help="Result id, usually source:session_id")
    resume_parser.add_argument("--source", help="Source when passing a bare session id")

    eval_parser = sub.add_parser("eval", help="Evaluate query-to-session retrieval quality")
    eval_parser.add_argument("eval_file", type=Path)
    eval_parser.add_argument("--limit", type=int, default=5)
    eval_parser.add_argument("--min-recall", type=float, default=0.9)
    eval_parser.add_argument("--timings", action="store_true", help="Include query timing summary")
    eval_parser.add_argument("--json", action="store_true", help="Emit JSON")

    bench_parser = sub.add_parser("bench", help="Benchmark query latency from an eval file")
    bench_parser.add_argument("eval_file", type=Path)
    bench_parser.add_argument("--limit", type=int, default=5)
    bench_parser.add_argument("--max-p95-ms", type=float, default=250.0)
    bench_parser.add_argument("--json", action="store_true", help="Emit JSON")

    stats_parser = sub.add_parser("stats", help="Show index counts")
    stats_parser.set_defaults(_stats=True)

    args = parser.parse_args(argv)

    if args.command == "sources":
        return cmd_sources(args)
    if args.command == "start":
        return cmd_start(args)
    if args.command in {"index", "refresh"}:
        return cmd_refresh(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "brief":
        return cmd_brief(args)
    if args.command == "resume":
        return cmd_resume(args)
    if args.command == "eval":
        return cmd_eval(args)
    if args.command == "bench":
        return cmd_bench(args)
    if args.command == "stats":
        return cmd_stats(args)
    return 2


def add_refresh_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", action="append", help="Source to refresh")
    parser.add_argument("--all", action="store_true", help="Refresh default sources plus custom profiles")
    parser.add_argument("--include", type=Path, action="append", default=[], help="Extra JSONL file or directory")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--limit-files", type=int, help="Limit files per source while testing")
    parser.add_argument("--reset", action="store_true", help="Reset the whole database before refreshing")
    parser.add_argument("--force", action="store_true", help="Refresh matching files even if unchanged")
    parser.add_argument("--days", type=float, help="Only scan files modified in the last N days")


def cmd_sources(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1

    if args.sources_command == "add":
        try:
            validate_source_name(args.name, reserved=set(SOURCE_NAMES) | {"custom"})
            validate_resume_template(args.resume_template)
        except ValueError as exc:
            print(str(exc))
            return 1

        profiles[args.name] = SourceProfile(
            name=args.name,
            paths=args.path,
            format=args.format,
            session_key=args.session_key,
            message_key=args.message_key,
            role_key=args.role_key,
            text_key=args.text_key,
            timestamp_key=args.timestamp_key,
            cwd_key=args.cwd_key,
            title_key=args.title_key,
            resume_template=args.resume_template,
        )
        save_profiles(profiles, args.config)
        print(f"Saved source profile: {args.name}")
        return 0

    if args.sources_command == "remove":
        if args.name not in profiles:
            print(f"No custom source profile found: {args.name}")
            return 1
        profiles.pop(args.name)
        save_profiles(profiles, args.config)
        print(f"Removed source profile: {args.name}")
        return 0

    rows = []
    for source, count, examples in describe_sources(home=args.home):
        rows.append(
            {
                "source": source,
                "kind": "builtin",
                "paths": count,
                "examples": [str(path) for path in examples],
            }
        )
    for profile in sorted(profiles.values(), key=lambda item: item.name):
        paths = source_profile_paths(profile)
        rows.append(
            {
                "source": profile.name,
                "kind": "custom",
                "format": profile.format,
                "paths": len(paths),
                "examples": [str(path) for path in paths[:5]],
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0

    for row in rows:
        marker = "custom" if row["kind"] == "custom" else "builtin"
        print(f"{row['source']}: {row['paths']} path(s) [{marker}]")
        for path in row["examples"]:
            print(f"  {path}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1
    selected_sources = selected_refresh_sources(args, profiles)
    store = ThreadStore(args.db)
    try:
        if args.reset:
            store.reset()
        report = refresh_store(
            store,
            selected_sources,
            profiles,
            home=args.home,
            limit_files=args.limit_files,
            force=args.force,
            days=args.days,
            include_paths=args.include,
        )
        if report["unknown_source"]:
            print(f"Unknown source: {report['unknown_source']}")
            return 1
        print_refresh_report(report, args.db)
        return 0
    finally:
        store.close()


def cmd_start(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1

    selected_sources = selected_refresh_sources(args, profiles)
    unknown_sources = unknown_selected_sources(selected_sources, profiles)
    if unknown_sources:
        print(f"Unknown source: {unknown_sources[0]}")
        return 1
    discovery_rows = source_discovery_rows(selected_sources, profiles, home=args.home)

    print("Threadlens setup")
    print(f"Index: {args.db}")
    print("Threadlens reads local transcripts and writes only its own SQLite search index.")
    print("Detected sources:")
    if discovery_rows:
        for row in discovery_rows:
            kind = "custom" if row["kind"] == "custom" else "builtin"
            print(f"  {row['source']}: {row['paths']} path(s) [{kind}]")
    else:
        print("  none")
    print("Indexing...")

    store = ThreadStore(args.db)
    try:
        if args.reset:
            store.reset()
        report = refresh_store(
            store,
            selected_sources,
            profiles,
            home=args.home,
            limit_files=args.limit_files,
            force=args.force,
            days=args.days,
            include_paths=args.include,
        )
        if report["unknown_source"]:
            print(f"Unknown source: {report['unknown_source']}")
            return 1
        print_refresh_report(report, args.db)
        total_messages = store.message_count()
        stats_rows = [dict(row) for row in store.stats()]
    finally:
        store.close()

    readiness = start_readiness_report(discovery_rows, stats_rows, report)
    if total_messages <= 0:
        print("Not ready: no searchable messages were indexed.")
        print("Run `threadlens doctor` for details.")
        return 1

    if readiness["status"] == "partial":
        print("Partially ready.")
        if readiness["missing_indexed_sources"]:
            print(f"Missing indexed sources: {', '.join(readiness['missing_indexed_sources'])}")
        if readiness["errored_sources"]:
            print(f"Sources with errors: {', '.join(readiness['errored_sources'])}")
        print("Run `threadlens doctor` for details.")
    else:
        print("Ready.")
    print("Try:")
    print('  threadlens search "raycast"')
    print('  threadlens search "error message"')
    return 0


def refresh_store(
    store: ThreadStore,
    selected_sources: list[str],
    profiles: dict[str, SourceProfile],
    *,
    home: Path,
    limit_files: int | None,
    force: bool,
    days: float | None,
    include_paths: list[Path],
) -> dict[str, Any]:
    batch: list[ThreadMessage] = []
    counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    errored: Counter[str] = Counter()
    errors: list[tuple[str, Path, str]] = []
    report: dict[str, Any] = {
        "added": 0,
        "counts": counts,
        "skipped": skipped,
        "errored": errored,
        "errors": errors,
        "unknown_source": "",
        "rebuilt_fts": False,
    }
    changed_files = 0

    def flush() -> int:
        if not batch:
            return 0
        added_count = store.add_messages(batch, rebuild=False, commit=False)
        batch.clear()
        return added_count

    for source in selected_sources:
        profile = profiles.get(source)
        if source in SOURCE_NAMES:
            paths = source_paths(source, home=home)
        elif profile:
            paths = source_profile_paths(profile)
        else:
            report["unknown_source"] = source
            return report
        if limit_files is not None:
            paths = paths[:limit_files]
        for path in filtered_paths(paths, days=days):
            messages = source_profile_messages(profile, path) if profile else iter_path_messages(source, path)
            indexed, message_count, error = index_file_safely(
                store,
                source,
                path,
                messages,
                batch,
                force=force,
            )
            if error:
                errored[source] += 1
                errors.append((source, path, error))
            elif indexed:
                counts[source] += message_count
                changed_files += 1
            else:
                skipped[source] += 1
            if len(batch) >= 1000:
                report["added"] += flush()

    if include_paths:
        paths = custom_jsonl_paths(include_paths)
        if limit_files is not None:
            paths = paths[:limit_files]
        for path in filtered_paths(paths, days=days):
            indexed, message_count, error = index_file_safely(
                store,
                "custom",
                path,
                custom_jsonl_messages(path),
                batch,
                force=force,
            )
            if error:
                errored["custom"] += 1
                errors.append(("custom", path, error))
            elif indexed:
                counts["custom"] += message_count
                changed_files += 1
            else:
                skipped["custom"] += 1
            if len(batch) >= 1000:
                report["added"] += flush()

    report["added"] += flush()
    if changed_files:
        store.rebuild_fts()
        report["rebuilt_fts"] = True
    store.conn.commit()
    return report


def print_refresh_report(
    report: dict[str, Any],
    db_path: Path,
    *,
    out=None,
    err=None,
) -> None:
    out = out or sys.stdout
    err = err or sys.stderr
    print(f"Refreshed {report['added']} message(s) into {db_path}", file=out)
    for source, count in sorted(report["counts"].items()):
        print(f"  {source}: {count}", file=out)
    for source, count in sorted(report["skipped"].items()):
        print(f"  {source} skipped unchanged files: {count}", file=out)
    for source, count in sorted(report["errored"].items()):
        print(f"  {source} skipped errored files: {count}", file=out)
    errors = report["errors"]
    for source, path, error in errors[:10]:
        print(f"  error: {source} {path}: {error}", file=err)
    if len(errors) > 10:
        print(f"  error: {len(errors) - 10} additional refresh file error(s) omitted", file=err)


def source_discovery_rows(
    selected_sources: list[str],
    profiles: dict[str, SourceProfile],
    *,
    home: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in selected_sources:
        if source in SOURCE_NAMES:
            paths = source_paths(source, home=home)
            rows.append({"source": source, "kind": "builtin", "paths": len(paths)})
        elif source in profiles:
            paths = source_profile_paths(profiles[source])
            rows.append({"source": source, "kind": "custom", "paths": len(paths)})
    return rows


def start_readiness_report(
    discovery_rows: list[dict[str, Any]],
    stats_rows: list[dict[str, Any]],
    refresh_report: dict[str, Any],
) -> dict[str, Any]:
    indexed_counts = {str(row["source"]): int(row["messages"]) for row in stats_rows}
    expected_sources = [
        str(row["source"])
        for row in discovery_rows
        if int(row.get("paths") or 0) > 0
    ]
    missing = [source for source in expected_sources if indexed_counts.get(source, 0) == 0]
    errored = sorted(str(source) for source, count in refresh_report["errored"].items() if count > 0)
    status = "partial" if missing or errored else "ready"
    return {
        "status": status,
        "missing_indexed_sources": missing,
        "errored_sources": errored,
    }


def load_profiles_for_cli(config_path: Path) -> dict[str, SourceProfile] | None:
    try:
        return load_profiles(config_path, strict=True)
    except ProfileConfigError as exc:
        print(f"Could not load source profile config: {exc}", file=sys.stderr)
        return None


def selected_refresh_sources(args: argparse.Namespace, profiles: dict[str, SourceProfile]) -> list[str]:
    if args.source:
        return args.source
    if args.all:
        return list(DEFAULT_SOURCE_NAMES) + sorted(profiles)
    return list(DEFAULT_SOURCE_NAMES)


def unknown_selected_sources(selected_sources: list[str], profiles: dict[str, SourceProfile]) -> list[str]:
    return [source for source in selected_sources if source not in SOURCE_NAMES and source not in profiles]


def filtered_paths(paths: list[Path], *, days: float | None) -> list[Path]:
    if days is None:
        return paths
    cutoff = time.time() - (days * 86400)
    filtered: list[Path] = []
    for path in paths:
        try:
            if path.stat().st_mtime >= cutoff:
                filtered.append(path)
        except OSError:
            continue
    return filtered


def index_file(
    store: ThreadStore,
    source: str,
    path: Path,
    messages,
    batch: list[ThreadMessage],
    *,
    force: bool,
) -> tuple[bool, int]:
    try:
        stat = path.stat()
    except OSError:
        return False, 0

    if not force and store.file_is_current(source, path, mtime_ns=stat.st_mtime_ns, size=stat.st_size):
        return False, 0

    store.delete_file(source, path)
    message_count = 0
    for message in messages:
        batch.append(message)
        message_count += 1
    store.mark_file_indexed(
        source,
        path,
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
        message_count=message_count,
    )
    return True, message_count


def index_file_safely(
    store: ThreadStore,
    source: str,
    path: Path,
    messages,
    batch: list[ThreadMessage],
    *,
    force: bool,
) -> tuple[bool, int, str | None]:
    batch_start = len(batch)
    store.conn.execute("savepoint refresh_file")
    try:
        indexed, message_count = index_file(
            store,
            source,
            path,
            messages,
            batch,
            force=force,
        )
    except sqlite3.Error:
        del batch[batch_start:]
        store.conn.execute("rollback to refresh_file")
        store.conn.execute("release refresh_file")
        raise
    except Exception as exc:  # noqa: BLE001 - refresh should report bad input files and continue.
        del batch[batch_start:]
        store.conn.execute("rollback to refresh_file")
        store.conn.execute("release refresh_file")
        return False, 0, str(exc) or exc.__class__.__name__
    store.conn.execute("release refresh_file")
    return indexed, message_count, None


def cmd_search(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1
    store = ThreadStore(args.db)
    try:
        if search_needs_bootstrap(store, args.source):
            if args.no_bootstrap:
                print(index_empty_message(args.source), file=sys.stderr)
                return 1
            selected_sources = [args.source] if args.source else list(DEFAULT_SOURCE_NAMES)
            target = f" for source {args.source}" if args.source else ""
            print(f"Index is empty{target}. Running first-time indexing...", file=sys.stderr)
            report = refresh_store(
                store,
                selected_sources,
                profiles,
                home=args.home,
                limit_files=None,
                force=False,
                days=None,
                include_paths=[],
            )
            if report["unknown_source"]:
                print(f"Unknown source: {report['unknown_source']}", file=sys.stderr)
                return 1
            print_refresh_report(report, args.db, out=sys.stderr, err=sys.stderr)

        try:
            results = store.search_sessions(
                " ".join(args.query),
                limit=args.limit,
                source=args.source,
                cwd_prefix=normalize_cwd_filter(args.cwd) if args.cwd else None,
            )
        except sqlite3.Error as exc:
            print(f"Search failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            for result in results:
                payload = with_actions(result, profiles)
                print(json.dumps(payload, ensure_ascii=False))
            return 0

        if not results:
            print("No results.")
            return 1

        for idx, result in enumerate(results, 1):
            result = with_actions(result, profiles)
            print(f"[{idx}] {result['source']} {result['session_id']} score={result['score']}")
            print(f"    title: {result['title'] or '-'}")
            print(f"    cwd: {result['cwd'] or '-'}")
            print(f"    last: {result['last_timestamp'] or '-'}")
            print(f"    result: {result['result_id']}")
            command = result["actions"].get("resume_command")
            if command:
                print(f"    resume: {command}")
            for snippet in result["best_snippets"]:
                print(f"    {snippet['role']} {snippet['timestamp']}: {snippet['snippet']}")
        return 0
    finally:
        store.close()


def search_needs_bootstrap(store: ThreadStore, source: str | None) -> bool:
    if source:
        return store.message_count(source) == 0
    return store.message_count() == 0


def normalize_cwd_filter(value: str) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def index_empty_message(source: str | None) -> str:
    if source:
        return f"No indexed messages for source {source}. Run `threadlens start` or `threadlens refresh --source {source}`."
    return "Index is empty. Run `threadlens start`."


def with_actions(result: dict[str, Any], profiles: dict[str, SourceProfile] | None = None) -> dict[str, Any]:
    payload = dict(result)
    actions = dict(payload.get("actions") or {})
    command = resume_command_for(payload["source"], payload["session_id"], payload.get("cwd") or "", profiles=profiles)
    if command:
        actions["resume_command"] = command
    actions["open_source"] = f"{payload['source_path']}:{payload['source_line']}"
    payload["actions"] = actions
    return payload


def resume_command_for(
    source: str,
    thread_id: str,
    cwd: str,
    *,
    profiles: dict[str, SourceProfile] | None = None,
) -> str:
    if not thread_id:
        return ""

    prefix = f"cd {shlex.quote(cwd)} && " if cwd else ""
    if source == "codex":
        return f"{prefix}codex resume {shlex.quote(thread_id)}"
    if source == "claude":
        return f"{prefix}claude --resume {shlex.quote(thread_id)}"
    if source == "pi":
        return f"{prefix}pi --session {shlex.quote(thread_id)}"
    if source == "omp":
        return f"{prefix}omp --resume {shlex.quote(thread_id)}"
    if source == "droid":
        return f"{prefix}droid --resume {shlex.quote(thread_id)}"
    if source == "opencode":
        return f"{prefix}opencode --session {shlex.quote(thread_id)}"
    profile = (profiles or {}).get(source)
    if profile and profile.resume_template:
        values = {
            "source": shlex.quote(source),
            "session_id": shlex.quote(thread_id),
            "cwd": shlex.quote(cwd),
        }
        try:
            return profile.resume_template.format_map(values)
        except (KeyError, ValueError):
            return ""
    return ""


def validate_resume_template(template: str) -> None:
    if not template:
        return
    try:
        fields = [field for _, field, _, _ in string.Formatter().parse(template) if field]
    except ValueError as exc:
        raise ValueError(f"Invalid resume template: {exc}") from exc
    for field in fields:
        root = field.split(".", 1)[0].split("[", 1)[0]
        if root not in RESUME_TEMPLATE_FIELDS:
            allowed = ", ".join(sorted(RESUME_TEMPLATE_FIELDS))
            raise ValueError(f"Resume template field is not supported: {root}. Use only: {allowed}")


def parse_result_id(result_id: str, source: str | None = None) -> tuple[str | None, str]:
    if source:
        return source, result_id
    if ":" in result_id:
        return result_id.split(":", 1)
    return None, result_id


def resolve_session(store: ThreadStore, result_id: str, source: str | None = None) -> tuple[str, str, list[Any]]:
    parsed_source, session_id = parse_result_id(result_id, source=source)
    if parsed_source:
        rows = store.get_session(parsed_source, session_id)
        if rows:
            return parsed_source, session_id, rows
        raise ValueError(f"No session found for {parsed_source}:{session_id}")

    matches = store.find_sessions(session_id)
    if not matches:
        raise ValueError(f"No session found for {session_id}")
    if len(matches) > 1:
        sources = ", ".join(f"{row['source']}:{row['thread_id']}" for row in matches)
        raise ValueError(f"Ambiguous session id. Use one of: {sources}")
    resolved_source = matches[0]["source"]
    rows = store.get_session(resolved_source, session_id)
    return resolved_source, session_id, rows


def cmd_doctor(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1
    report = []
    for source in SOURCE_NAMES:
        paths = source_paths(source, home=args.home)
        readable = 0
        parsed = 0
        errors = []
        path_fingerprints = []
        for path in paths:
            try:
                stat = path.stat()
                readable += 1
                path_fingerprints.append(
                    {
                        "source": source,
                        "path": str(path),
                        "mtime_ns": stat.st_mtime_ns,
                        "size": stat.st_size,
                    }
                )
                first = next(iter_path_messages(source, path), None)
                if first is not None:
                    parsed += 1
            except Exception as exc:  # noqa: BLE001 - doctor should report and continue.
                errors.append({"path": str(path), "error": str(exc)})
        report.append(
            {
                "source": source,
                "paths": len(paths),
                "readable_paths": readable,
                "paths_with_messages": parsed,
                "errors": errors[:5],
                "status": "ok" if readable == len(paths) and not errors else "degraded",
                "_path_fingerprints": path_fingerprints,
            }
        )
    for profile in sorted(profiles.values(), key=lambda item: item.name):
        paths = source_profile_paths(profile)
        readable = 0
        parsed = 0
        errors = []
        path_fingerprints = []
        for path in paths:
            try:
                stat = path.stat()
                readable += 1
                path_fingerprints.append(
                    {
                        "source": profile.name,
                        "path": str(path),
                        "mtime_ns": stat.st_mtime_ns,
                        "size": stat.st_size,
                    }
                )
                first = next(source_profile_messages(profile, path), None)
                if first is not None:
                    parsed += 1
            except Exception as exc:  # noqa: BLE001 - doctor should report and continue.
                errors.append({"path": str(path), "error": str(exc)})
        report.append(
            {
                "source": profile.name,
                "kind": "custom",
                "paths": len(paths),
                "readable_paths": readable,
                "paths_with_messages": parsed,
                "errors": errors[:5],
                "status": "ok" if readable == len(paths) and not errors else "degraded",
                "_path_fingerprints": path_fingerprints,
            }
        )

    index = index_readiness_report(args.db, report)
    if args.json:
        public_report = public_source_report(report)
        print(json.dumps({"sources": public_report, "index": index, "ready": index["status"] == "ready"}, ensure_ascii=False))
        return 0

    print("Sources")
    for item in report:
        print(f"  {item['source']}: {item['status']} ({item['paths_with_messages']}/{item['paths']} paths with messages)")
        for error in item["errors"]:
            print(f"  error: {error['path']} {error['error']}")
    print("Index")
    print(f"  db: {index['db']}")
    print(f"  status: {index['status']}")
    print(f"  messages: {index['messages']}")
    for source in index["sources"]:
        print(f"  {source['source']}: {source['messages']} messages, {source['threads']} threads")
    if index["missing_indexed_sources"]:
        print(f"  missing indexed sources: {', '.join(index['missing_indexed_sources'])}")
    freshness = index.get("freshness") or {}
    if freshness.get("missing_files") or freshness.get("stale_files") or freshness.get("deleted_files"):
        print(
            "  freshness: "
            f"{freshness.get('missing_files', 0)} missing, "
            f"{freshness.get('stale_files', 0)} stale, "
            f"{freshness.get('deleted_files', 0)} deleted"
        )
        for sample in freshness.get("samples", [])[:5]:
            print(f"  stale: {sample['source']} {sample['path']} ({sample['reason']})")
        if freshness.get("action"):
            print(f"  freshness action: {freshness['action']}")
    if index["action"]:
        print(f"  action: {index['action']}")
    return 0


def public_source_report(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in report
    ]


def index_readiness_report(db_path: Path, source_report: list[dict[str, Any]]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "db": str(db_path),
        "exists": db_path.exists(),
        "status": "not_ready",
        "messages": 0,
        "sources": [],
        "missing_indexed_sources": [],
        "freshness": {
            "status": "fresh",
            "missing_files": 0,
            "stale_files": 0,
            "deleted_files": 0,
            "action": "",
            "samples": [],
        },
        "action": "run: threadlens start",
        "error": "",
    }
    if not db_path.exists():
        return base

    try:
        uri_path = urllib.parse.quote(str(db_path), safe="/:")
        conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        base["status"] = "error"
        base["error"] = str(exc)
        return base

    try:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type = 'table'")
        }
        messages_table = conn.execute(
            "select 1 from sqlite_master where type = 'table' and name = 'messages'"
        ).fetchone()
        if messages_table is None:
            return base

        rows = list(
            conn.execute(
                """
                select source, count(*) as messages, count(distinct thread_id) as threads
                from messages
                group by source
                order by source
                """
            )
        )
        sources = [
            {"source": row["source"], "messages": int(row["messages"]), "threads": int(row["threads"])}
            for row in rows
        ]
        total = sum(row["messages"] for row in sources)
        indexed_counts = {row["source"]: row["messages"] for row in sources}
        expected_sources = [
            item["source"]
            for item in source_report
            if item.get("paths_with_messages", 0) > 0
        ]
        missing = [source for source in expected_sources if indexed_counts.get(source, 0) == 0]
        indexed_files = []
        if "indexed_files" in tables:
            indexed_files = [
                dict(row)
                for row in conn.execute(
                    """
                    select source, path, mtime_ns, size, message_count, indexed_at
                    from indexed_files
                    """
                )
            ]
        freshness = index_freshness_report(source_report, indexed_files)

        base["messages"] = total
        base["sources"] = sources
        base["missing_indexed_sources"] = missing
        base["freshness"] = freshness
        if total <= 0:
            base["status"] = "not_ready"
            base["action"] = "run: threadlens start"
        elif missing:
            base["status"] = "partial"
            base["action"] = "run: threadlens start"
        else:
            base["status"] = "ready"
            base["action"] = ""
        return base
    except sqlite3.Error as exc:
        base["status"] = "error"
        base["error"] = str(exc)
        return base
    finally:
        conn.close()


def index_freshness_report(source_report: list[dict[str, Any]], indexed_files: list[dict[str, Any]]) -> dict[str, Any]:
    expected: dict[tuple[str, str], dict[str, Any]] = {}
    for item in source_report:
        for fingerprint in item.get("_path_fingerprints", []):
            key = (str(fingerprint["source"]), str(fingerprint["path"]))
            expected[key] = fingerprint

    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in indexed_files:
        key = (str(row["source"]), str(row["path"]))
        indexed[key] = row

    samples: list[dict[str, str]] = []
    missing_files = 0
    stale_files = 0
    deleted_files = 0

    for key, fingerprint in expected.items():
        row = indexed.get(key)
        if row is None:
            missing_files += 1
            add_freshness_sample(samples, key, "not indexed")
            continue
        if int(row.get("mtime_ns") or 0) != int(fingerprint.get("mtime_ns") or 0) or int(row.get("size") or 0) != int(fingerprint.get("size") or 0):
            stale_files += 1
            add_freshness_sample(samples, key, "changed")

    for key in indexed:
        if key not in expected:
            deleted_files += 1
            add_freshness_sample(samples, key, "missing source file")

    return {
        "status": "stale" if missing_files or stale_files or deleted_files else "fresh",
        "missing_files": missing_files,
        "stale_files": stale_files,
        "deleted_files": deleted_files,
        "action": "run: threadlens refresh" if missing_files or stale_files or deleted_files else "",
        "samples": samples,
    }


def add_freshness_sample(samples: list[dict[str, str]], key: tuple[str, str], reason: str) -> None:
    if len(samples) >= 10:
        return
    source, path = key
    samples.append({"source": source, "path": path, "reason": reason})


def cmd_brief(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1
    store = ThreadStore(args.db)
    try:
        try:
            source, session_id, rows = resolve_session(store, args.result_id, source=args.source)
        except ValueError as exc:
            print(str(exc))
            return 1

        brief = build_brief(source, session_id, rows, profiles=profiles)
        if args.json:
            print(json.dumps(brief, ensure_ascii=False))
            return 0

        print(f"{brief['source']}:{brief['session_id']}")
        print(f"title: {brief['title'] or '-'}")
        print(f"cwd: {brief['cwd'] or '-'}")
        print(f"messages: {brief['message_count']}")
        print(f"last: {brief['last_timestamp'] or '-'}")
        if brief["resume_command"]:
            print(f"resume: {brief['resume_command']}")
        if brief["last_user_message"]:
            print(f"last user: {brief['last_user_message']}")
        if brief["last_assistant_message"]:
            print(f"last assistant: {brief['last_assistant_message']}")
        return 0
    finally:
        store.close()


def cmd_resume(args: argparse.Namespace) -> int:
    profiles = load_profiles_for_cli(args.config)
    if profiles is None:
        return 1
    store = ThreadStore(args.db)
    try:
        try:
            source, session_id, rows = resolve_session(store, args.result_id, source=args.source)
        except ValueError as exc:
            print(str(exc))
            return 1
        cwd = first_non_empty(rows, "cwd")
        command = resume_command_for(source, session_id, cwd, profiles=profiles)
        if not command:
            print(f"No verified resume command for source: {source}")
            return 1
        print(command)
        return 0
    finally:
        store.close()


def cmd_eval(args: argparse.Namespace) -> int:
    try:
        cases = load_eval_cases(args.eval_file)
    except ValueError as exc:
        print(f"Could not read eval file: {exc}")
        return 1

    store = ThreadStore(args.db)
    try:
        positive_total = 0
        positive_hits = 0
        negative_total = 0
        negative_failures = 0
        case_results = []
        durations_ms: list[float] = []

        for case in cases:
            targets = eval_case_targets(case)
            if not targets:
                continue
            target_source, target_session = targets[0]

            positives = []
            for query in case.get("queries", []):
                started = perf_counter()
                try:
                    results = store.search_sessions(query, limit=args.limit)
                except sqlite3.Error as exc:
                    print(f"Eval search failed: {exc}", file=sys.stderr)
                    return 1
                duration_ms = (perf_counter() - started) * 1000
                durations_ms.append(duration_ms)
                hit_rank = rank_for_targets(results, targets)
                positive_total += 1
                if hit_rank is not None:
                    positive_hits += 1
                entry = {"query": query, "hit_rank": hit_rank}
                if args.timings:
                    entry["duration_ms"] = round(duration_ms, 3)
                positives.append(entry)

            negatives = []
            for query in case.get("negative_queries", []):
                started = perf_counter()
                try:
                    results = store.search_sessions(query, limit=args.limit)
                except sqlite3.Error as exc:
                    print(f"Eval search failed: {exc}", file=sys.stderr)
                    return 1
                duration_ms = (perf_counter() - started) * 1000
                durations_ms.append(duration_ms)
                hit_rank = rank_for_targets(results, targets)
                negative_total += 1
                if hit_rank is not None:
                    negative_failures += 1
                entry = {"query": query, "hit_rank": hit_rank}
                if args.timings:
                    entry["duration_ms"] = round(duration_ms, 3)
                negatives.append(entry)

            case_results.append(
                {
                    "case_id": case.get("case_id") or f"{target_source}:{target_session}",
                    "target": {"source": target_source, "session_id": target_session},
                    "targets": [{"source": source, "session_id": session_id} for source, session_id in targets],
                    "positives": positives,
                    "negatives": negatives,
                }
            )

        recall = positive_hits / positive_total if positive_total else 0.0
        passed = recall >= args.min_recall and negative_failures == 0
        report = {
            "passed": passed,
            "recall_at_limit": recall,
            "positive_hits": positive_hits,
            "positive_total": positive_total,
            "negative_failures": negative_failures,
            "negative_total": negative_total,
            "limit": args.limit,
            "cases": case_results,
        }
        if args.timings:
            report["timings_ms"] = timing_summary(durations_ms)

        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"passed: {passed}")
            print(f"recall@{args.limit}: {positive_hits}/{positive_total} = {recall:.3f}")
            print(f"negative failures: {negative_failures}/{negative_total}")
            if args.timings:
                summary = report["timings_ms"]
                print(
                    "timings: "
                    f"count={summary['count']} "
                    f"p50={summary['p50']:.1f}ms "
                    f"p95={summary['p95']:.1f}ms "
                    f"max={summary['max']:.1f}ms"
                )
            for case in case_results:
                print(f"- {case['case_id']}")
                for positive in case["positives"]:
                    suffix = f", {positive['duration_ms']:.1f}ms" if args.timings else ""
                    print(f"  + {positive['query']}: rank {positive['hit_rank']}{suffix}")
                for negative in case["negatives"]:
                    suffix = f", {negative['duration_ms']:.1f}ms" if args.timings else ""
                    print(f"  - {negative['query']}: target rank {negative['hit_rank']}{suffix}")
        return 0 if passed else 1
    finally:
        store.close()


def cmd_bench(args: argparse.Namespace) -> int:
    try:
        cases = load_eval_cases(args.eval_file)
    except ValueError as exc:
        print(f"Could not read eval file: {exc}")
        return 1

    queries = eval_queries(cases)
    store = ThreadStore(args.db)
    try:
        rows = []
        for query in queries:
            started = perf_counter()
            try:
                store.search_sessions(query, limit=args.limit)
            except sqlite3.Error as exc:
                print(f"Bench search failed: {exc}", file=sys.stderr)
                return 1
            duration_ms = (perf_counter() - started) * 1000
            rows.append({"query": query, "duration_ms": round(duration_ms, 3)})

        summary = timing_summary([row["duration_ms"] for row in rows])
        passed = summary["p95"] <= args.max_p95_ms
        report = {
            "passed": passed,
            "max_p95_ms": args.max_p95_ms,
            "timings_ms": summary,
            "slowest": sorted(rows, key=lambda row: row["duration_ms"], reverse=True)[:10],
        }

        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"passed: {passed}")
            print(
                "timings: "
                f"count={summary['count']} "
                f"p50={summary['p50']:.1f}ms "
                f"p95={summary['p95']:.1f}ms "
                f"max={summary['max']:.1f}ms"
            )
            for row in report["slowest"]:
                print(f"  {row['duration_ms']:.1f}ms {row['query']}")
        return 0 if passed else 1
    finally:
        store.close()


def load_eval_cases(path: Path) -> list[dict[str, Any]]:
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(cases, list):
        raise ValueError("Eval file must contain a JSON array")
    return [case for case in cases if isinstance(case, dict)]


def eval_queries(cases: list[dict[str, Any]]) -> list[str]:
    queries: list[str] = []
    for case in cases:
        queries.extend(str(query) for query in case.get("queries", []) if str(query).strip())
        queries.extend(str(query) for query in case.get("negative_queries", []) if str(query).strip())
    return queries


def timing_summary(durations_ms: list[float]) -> dict[str, float | int]:
    if not durations_ms:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    ordered = sorted(durations_ms)
    return {
        "count": len(ordered),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "max": max(ordered),
        "mean": sum(ordered) / len(ordered),
    }


def percentile(ordered_values: list[float], fraction: float) -> float:
    if not ordered_values:
        return 0.0
    index = min(len(ordered_values) - 1, max(0, int(round((len(ordered_values) - 1) * fraction))))
    return ordered_values[index]


def build_brief(
    source: str,
    session_id: str,
    rows: list[Any],
    *,
    profiles: dict[str, SourceProfile] | None = None,
) -> dict[str, Any]:
    row_dicts = [dict(row) for row in rows]
    first = row_dicts[0] if row_dicts else {}
    last = row_dicts[-1] if row_dicts else {}
    cwd = first_non_empty(rows, "cwd")
    return {
        "source": source,
        "session_id": session_id,
        "title": first.get("title") or "",
        "cwd": cwd,
        "message_count": len(row_dicts),
        "first_timestamp": first.get("timestamp") or "",
        "last_timestamp": last.get("timestamp") or "",
        "source_path": first.get("path") or "",
        "resume_command": resume_command_for(source, session_id, cwd, profiles=profiles),
        "first_user_message": compact_for_display(first_role_text(row_dicts, "user")),
        "last_user_message": compact_for_display(last_role_text(row_dicts, "user")),
        "last_assistant_message": compact_for_display(last_role_text(row_dicts, "assistant")),
    }


def first_non_empty(rows: list[Any], field: str) -> str:
    for row in rows:
        value = row[field]
        if value:
            return str(value)
    return ""


def first_role_text(rows: list[dict[str, Any]], role: str) -> str:
    for row in rows:
        if row.get("role") == role:
            return row.get("text") or ""
    return ""


def last_role_text(rows: list[dict[str, Any]], role: str) -> str:
    for row in reversed(rows):
        if row.get("role") == role:
            return row.get("text") or ""
    return ""


def compact_for_display(text: str, limit: int = 320) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def rank_for_target(results: list[dict[str, Any]], source: str, session_id: str) -> int | None:
    for index, result in enumerate(results, 1):
        if result["source"] == source and result["session_id"] == session_id:
            return index
    return None


def rank_for_targets(results: list[dict[str, Any]], targets: list[tuple[str, str]]) -> int | None:
    target_set = set(targets)
    for index, result in enumerate(results, 1):
        if (result["source"], result["session_id"]) in target_set:
            return index
    return None


def eval_case_targets(case: dict[str, Any]) -> list[tuple[str, str]]:
    raw_targets = case.get("targets")
    if isinstance(raw_targets, list):
        targets = [eval_target_tuple(target) for target in raw_targets if isinstance(target, dict)]
        return [target for target in targets if target[0] and target[1]]

    target = case.get("target") if isinstance(case.get("target"), dict) else {}
    source = target.get("source") or case.get("source")
    session_id = target.get("session_id") or target.get("thread_id") or case.get("target_thread_id")
    if not source or not session_id:
        return []
    return [(str(source), str(session_id))]


def eval_target_tuple(target: dict[str, Any]) -> tuple[str, str]:
    source = target.get("source")
    session_id = target.get("session_id") or target.get("thread_id")
    return str(source or ""), str(session_id or "")


def cmd_stats(args: argparse.Namespace) -> int:
    store = ThreadStore(args.db)
    try:
        rows = store.stats()
        if not rows:
            print("No indexed messages.")
            return 0
        for row in rows:
            print(f"{row['source']}: {row['messages']} message(s), {row['threads']} thread(s)")
        return 0
    finally:
        store.close()
