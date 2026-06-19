"""tests/test_freshness.py — per-source index-freshness feature."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from threadlens.cli import main
from threadlens.models import ThreadMessage
from threadlens.sources import DEFAULT_SOURCE_NAMES
from threadlens.store import ThreadStore


# ---------------------------------------------------------------------------
# Helpers shared across test cases
# ---------------------------------------------------------------------------

def _make_message(
    *,
    source: str = "codex",
    thread_id: str = "t1",
    message_id: str = "m1",
    path: Path | None = None,
    text: str = "sample text",
) -> ThreadMessage:
    return ThreadMessage(
        source=source,
        thread_id=thread_id,
        message_id=message_id,
        path=path or Path("/tmp/f.jsonl"),
        line=1,
        timestamp="2026-06-17T00:00:00Z",
        role="user",
        cwd="/tmp/project",
        title="test session",
        text=text,
    )


def _seed_store(db: Path, messages: list[ThreadMessage]) -> None:
    store = ThreadStore(db)
    try:
        store.add_messages(messages)
    finally:
        store.close()


def _write_codex_session(home: Path, *, text: str = "alpha setup phrase") -> Path:
    session_dir = home / ".codex" / "sessions"
    session_dir.mkdir(parents=True)
    path = session_dir / "rollout.jsonl"
    rows = [
        {
            "type": "session_meta",
            "timestamp": "2026-06-17T00:00:00Z",
            "payload": {"id": "codex-session", "cwd": "/tmp/threadlens-test"},
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-17T00:01:00Z",
            "payload": {
                "id": "msg-user",
                "type": "message",
                "role": "user",
                "content": [{"text": text}],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# a. Store unit tests: mark_sources_checked / source_freshness
# ---------------------------------------------------------------------------

class FreshnessStoreTests(unittest.TestCase):

    def test_mark_then_read_all_sources_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                at = "2026-06-19T10:00:00+00:00"
                store.mark_sources_checked(["codex", "claude"], at)
                freshness = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertTrue(freshness["known"])
        self.assertEqual(freshness["oldest_checked_at"], at)
        self.assertEqual(freshness["per_source"], {"codex": at, "claude": at})

    def test_missing_row_gives_known_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.mark_sources_checked(["codex"], "2026-06-19T10:00:00+00:00")
                freshness = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertFalse(freshness["known"])
        self.assertIsNone(freshness["per_source"]["claude"])
        self.assertIsNotNone(freshness["per_source"]["codex"])

    def test_oldest_checked_at_is_minimum_over_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                newer = "2026-06-19T10:00:00+00:00"
                older = "2026-06-18T10:00:00+00:00"
                store.mark_sources_checked(["codex"], newer)
                store.mark_sources_checked(["claude"], older)
                freshness = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertTrue(freshness["known"])
        self.assertEqual(freshness["oldest_checked_at"], older)

    def test_empty_sources_list_gives_known_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                freshness = store.source_freshness([])
            finally:
                store.close()

        self.assertFalse(freshness["known"])
        self.assertIsNone(freshness["oldest_checked_at"])

    def test_no_rows_gives_known_false_and_none_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                freshness = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertFalse(freshness["known"])
        self.assertIsNone(freshness["oldest_checked_at"])
        for v in freshness["per_source"].values():
            self.assertIsNone(v)

    def test_mark_is_upsert_not_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.mark_sources_checked(["codex"], "2020-01-01T00:00:00+00:00")
                store.mark_sources_checked(["codex"], "2026-06-19T10:00:00+00:00")
                freshness = store.source_freshness(["codex"])
            finally:
                store.close()

        self.assertEqual(freshness["oldest_checked_at"], "2026-06-19T10:00:00+00:00")


# ---------------------------------------------------------------------------
# b. refresh records last_checked_at even when all files are skipped
# ---------------------------------------------------------------------------

class FreshnessRefreshTests(unittest.TestCase):

    def test_refresh_marks_sources_even_when_all_files_skipped(self):
        """Second refresh with no changed files still records last_checked_at."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home)
            config = root / "sources.json"
            db = root / "index.sqlite"

            # First run — actually indexes
            code1, _, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "refresh", "--home", str(home)]
            )
            self.assertEqual(code1, 0)

            # Overwrite freshness with old sentinel so the second run's update is detectable
            store = ThreadStore(db)
            try:
                store.mark_sources_checked(list(DEFAULT_SOURCE_NAMES), "2020-01-01T00:00:00+00:00")
            finally:
                store.close()

            # Second run — all files unchanged (skipped)
            code2, _, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "refresh", "--home", str(home)]
            )
            self.assertEqual(code2, 0)

            store = ThreadStore(db)
            try:
                freshness = store.source_freshness(list(DEFAULT_SOURCE_NAMES))
            finally:
                store.close()

        # codex at minimum must have been updated past the old sentinel
        codex_ts = freshness["per_source"].get("codex")
        self.assertIsNotNone(codex_ts)
        self.assertGreater(codex_ts, "2020-01-01T00:00:00+00:00")

    # c. partial refresh --source codex marks ONLY codex
    def test_partial_refresh_marks_only_requested_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, _, _ = _run_cli(
                [
                    "--db", str(db), "--config", str(config),
                    "refresh", "--source", "codex", "--home", str(home),
                ]
            )
            self.assertEqual(code, 0)

            store = ThreadStore(db)
            try:
                freshness = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertIsNotNone(freshness["per_source"]["codex"])
        self.assertIsNone(freshness["per_source"]["claude"])
        # claude is unknown, so known must be False
        self.assertFalse(freshness["known"])


# ---------------------------------------------------------------------------
# d. Human search output: last checked / stale nudge / freshness unknown
# ---------------------------------------------------------------------------

class FreshnessSearchHumanTests(unittest.TestCase):

    def test_search_shows_last_checked_when_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="zebra deployment phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            _run_cli(["--db", str(db), "--config", str(config), "refresh", "--home", str(home)])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "zebra deployment"]
            )

        self.assertIn("index: last checked", stdout)

    def test_search_shows_stale_nudge_for_old_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            _seed_store(db, [_make_message(text="delta stale phrase")])

            # Seed a very old timestamp
            store = ThreadStore(db)
            try:
                store.mark_sources_checked(list(DEFAULT_SOURCE_NAMES), "2020-01-01T00:00:00+00:00")
            finally:
                store.close()

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "delta stale"]
            )

        self.assertIn("last checked", stdout)
        self.assertIn("stale", stdout)
        self.assertIn("threadlens refresh", stdout)

    def test_search_shows_freshness_unknown_when_no_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            _seed_store(db, [_make_message(text="gamma widget phrase")])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "gamma widget"]
            )

        self.assertIn("freshness unknown", stdout)

    def test_search_no_results_still_shows_freshness_line(self):
        """'No results.' path also prints a freshness line."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            _seed_store(db, [_make_message(text="some irrelevant content")])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "completelymadeuptermxyz99"]
            )

        self.assertIn("No results.", stdout)
        # freshness unknown because no source_refresh_state rows
        self.assertIn("freshness", stdout)


# ---------------------------------------------------------------------------
# e. search --json: result fields + score + no stray metadata lines
# ---------------------------------------------------------------------------

class FreshnessJsonTests(unittest.TestCase):

    def test_json_results_have_freshness_fields_and_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="omega protocol phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            _run_cli(["--db", str(db), "--config", str(config), "refresh", "--home", str(home)])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--json",
                 "--no-bootstrap", "--home", str(home), "omega protocol"]
            )

        lines = [line for line in stdout.splitlines() if line.strip()]
        self.assertGreater(len(lines), 0, "Expected at least one result")
        for line in lines:
            obj = json.loads(line)
            self.assertIn("index_checked_at", obj)
            self.assertIn("index_age_seconds", obj)
            self.assertIn("score", obj)

    def test_json_no_stray_metadata_line_on_empty_results(self):
        """--json with zero results emits zero stdout lines (no metadata object)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            _seed_store(db, [_make_message(text="noise irrelevant text")])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--json",
                 "--no-bootstrap", "--home", str(home), "completelymadeuptermxyz99"]
            )

        # All non-empty stdout lines must be valid JSON result objects
        for line in stdout.splitlines():
            if line.strip():
                obj = json.loads(line)
                # Must be a result object, not a bare metadata dict
                self.assertIn("result_id", obj)
        # No output at all for zero-result --json
        self.assertEqual(stdout.strip(), "")

    def test_json_freshness_fields_present_with_no_freshness_rows(self):
        """index_checked_at=null, index_age_seconds=null when table is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            _seed_store(db, [_make_message(text="kappa trace phrase")])

            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--json",
                 "--no-bootstrap", "--home", str(home), "kappa trace"]
            )

        lines = [line for line in stdout.splitlines() if line.strip()]
        self.assertGreater(len(lines), 0)
        for line in lines:
            obj = json.loads(line)
            self.assertIsNone(obj["index_checked_at"])
            self.assertIsNone(obj["index_age_seconds"])


# ---------------------------------------------------------------------------
# f. search --fresh refreshes then records recent freshness
# ---------------------------------------------------------------------------

class FreshnessFreshFlagTests(unittest.TestCase):

    def test_fresh_flag_records_recent_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="lambda compute phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            # Pre-index so --fresh doesn't trigger bootstrap path
            _run_cli(["--db", str(db), "--config", str(config), "refresh", "--home", str(home)])

            # Clear freshness so we can confirm --fresh repopulates it
            store = ThreadStore(db)
            try:
                store.conn.execute("delete from source_refresh_state")
                store.conn.commit()
            finally:
                store.close()

            code, _, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--fresh",
                 "--no-bootstrap", "--home", str(home), "lambda compute"]
            )

            store = ThreadStore(db)
            try:
                freshness = store.source_freshness(list(DEFAULT_SOURCE_NAMES))
            finally:
                store.close()

        oldest = freshness["oldest_checked_at"]
        self.assertIsNotNone(oldest)
        then = datetime.fromisoformat(oldest)
        age_secs = (datetime.now(timezone.utc) - then).total_seconds()
        self.assertLess(age_secs, 60)


# ---------------------------------------------------------------------------
# g. Back-compat: missing table → freshness unknown, no crash
# ---------------------------------------------------------------------------

class FreshnessBackCompatTests(unittest.TestCase):

    def test_missing_table_gives_freshness_unknown_no_crash(self):
        """Old DB without source_refresh_state: auto-migrated on open, empty → unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            # Seed an indexed message
            _seed_store(db, [_make_message(text="backcompat legacy phrase")])

            # Simulate an old DB by dropping the freshness table
            store = ThreadStore(db)
            try:
                store.conn.execute("drop table source_refresh_state")
                store.conn.commit()
            finally:
                store.close()

            # Re-opening via cmd_search will run executescript(SCHEMA) → recreates table empty
            code, stdout, stderr = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "backcompat legacy"]
            )

        # exit 0 (found) or 1 (not found) — both are OK; must not crash
        self.assertIn(code, (0, 1))
        # Empty table → freshness unknown
        self.assertIn("freshness unknown", stdout)
        # No unexpected stderr (bootstrap messages from search are OK but should be empty here)
        self.assertEqual(stderr, "")

    def test_source_freshness_tolerates_missing_table_directly(self):
        """source_freshness handles OperationalError if called before __init__ creates the table."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.conn.execute("drop table source_refresh_state")
                result = store.source_freshness(["codex", "claude"])
            finally:
                store.close()

        self.assertFalse(result["known"])
        self.assertIsNone(result["oldest_checked_at"])
        for v in result["per_source"].values():
            self.assertIsNone(v)


# ---------------------------------------------------------------------------
# New tests required by reviewer fixes
# ---------------------------------------------------------------------------

class FreshnessFreshOrderingTests(unittest.TestCase):
    """Tests for fix #1: --fresh runs BEFORE the bootstrap guard."""

    # 5a. --fresh on empty index (no pre-indexing): refreshes + finds results
    def test_fresh_on_empty_index_refreshes_and_finds_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="zeta fresh empty phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            # No pre-indexing — index starts empty
            code, stdout, stderr = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--fresh",
                 "--home", str(home), "zeta fresh empty"]
            )

        # --fresh populated the index; search must succeed and find the session
        self.assertEqual(code, 0, f"Expected 0 but got {code}. stdout={stdout!r} stderr={stderr!r}")
        self.assertNotIn("Index is empty", stderr)

    # 5b. --fresh --no-bootstrap on empty index: still refreshes + searches (must NOT exit empty)
    def test_fresh_no_bootstrap_on_empty_index_still_searches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="eta fresh noboot phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            # --no-bootstrap should NOT block --fresh from running
            code, stdout, stderr = _run_cli(
                ["--db", str(db), "--config", str(config), "search", "--fresh", "--no-bootstrap",
                 "--home", str(home), "eta fresh noboot"]
            )

        # --fresh populated the index before the no-bootstrap guard fires;
        # since the index is now non-empty the guard is skipped and search runs.
        # Exit 0 means results found; exit 1 means no-results (acceptable too).
        # What is NOT acceptable: the "Index is empty" error message from --no-bootstrap.
        self.assertNotIn("No indexed messages", stderr, "no-bootstrap guard must not fire when --fresh ran first")
        self.assertNotIn("Index is empty", stderr)

    # 5c. unfiltered freshness scope: custom source not in defaults → known=False
    def test_unfiltered_freshness_covers_non_default_sources(self):
        """indexed_sources includes a custom source; marking only defaults leaves known=False."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            config = root / "sources.json"
            db = root / "index.sqlite"

            # Seed: one default (codex) and one non-default (mybot) source
            store = ThreadStore(db)
            try:
                store.add_messages([
                    _make_message(source="codex", thread_id="t10", message_id="m10",
                                  text="theta custom freshness"),
                    _make_message(source="mybot", thread_id="t11", message_id="m11",
                                  text="theta custom freshness"),
                ])
                # Mark ONLY the default sources as checked
                store.mark_sources_checked(list(DEFAULT_SOURCE_NAMES), "2026-06-19T10:00:00+00:00")
            finally:
                store.close()

            # Unfiltered search (source=None) → indexed_sources() returns ["codex","mybot"]
            # mybot has no freshness row → known must be False
            _, stdout, _ = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--no-bootstrap", "--home", str(home), "theta custom"]
            )

        # If known=False, print_freshness prints "freshness unknown", not "last checked"
        self.assertIn("freshness unknown", stdout,
                      "unfiltered scope must reflect the unchecked custom source")
        self.assertNotIn("last checked", stdout)

    # 5d. source_freshness re-raises non-missing-table OperationalError
    def test_source_freshness_reraises_non_missing_table_error(self):
        import sqlite3 as _sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            real_conn = store.conn

            # Proxy replaces store.conn; delegates everything except the target query.
            class _LockedProxy:
                def __getattr__(self, name: str):
                    return getattr(real_conn, name)

                def execute(self, sql: str, *args, **kwargs):
                    if "source_refresh_state" in sql:
                        raise _sqlite3.OperationalError("database is locked")
                    return real_conn.execute(sql, *args, **kwargs)

            store.conn = _LockedProxy()  # type: ignore[assignment]
            try:
                with self.assertRaises(_sqlite3.OperationalError) as ctx:
                    store.source_freshness(["codex"])
                self.assertIn("database is locked", str(ctx.exception))
            finally:
                store.conn = real_conn
                store.close()

class FreshnessBootstrapMarkTests(unittest.TestCase):
    """Bootstrap path (first-run auto-index) must record freshness."""

    def test_bootstrap_search_shows_last_checked_not_unknown(self):
        """Empty index + search without --no-bootstrap → auto-indexes → freshness known."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            _write_codex_session(home, text="iota bootstrap phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            # No pre-indexing; bootstrap path fires automatically
            code, stdout, stderr = _run_cli(
                ["--db", str(db), "--config", str(config), "search",
                 "--home", str(home), "iota bootstrap"]
            )

        self.assertEqual(code, 0, f"Expected results. stdout={stdout!r} stderr={stderr!r}")
        self.assertIn("index: last checked", stdout)
        self.assertNotIn("freshness unknown", stdout)

class FreshnessUpgradeFromOldDbTests(unittest.TestCase):
    """A pre-freshness (v1.1.x) DB opened under the current schema must gain
    source_refresh_state automatically, without disturbing existing data."""

    OLD_SCHEMA = (
        "create table if not exists messages (id integer primary key, doc_key text not null unique, source text not null, thread_id text not null, message_id text not null, path text not null, line integer not null, timestamp text not null, role text not null, cwd text not null, title text not null, text text not null, metadata_json text not null);"
        "create table if not exists indexed_files (source text not null, path text not null, mtime_ns integer not null, size integer not null, message_count integer not null, indexed_at text not null default current_timestamp, primary key (source, path));"
        "create virtual table if not exists messages_fts using fts5(text, title, cwd, source, role, content='messages', content_rowid='id');"
    )

    def test_open_old_db_adds_table_and_preserves_data(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.sqlite"
            # v1.1.x DB: old schema, one indexed message, NO source_refresh_state.
            raw = sqlite3.connect(str(db))
            raw.executescript(self.OLD_SCHEMA)
            raw.execute(
                "insert into messages (doc_key,source,thread_id,message_id,path,line,timestamp,role,cwd,title,text,metadata_json)"
                " values (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("k1", "codex", "t1", "m1", "/p", 1, "2026-01-01T00:00:00Z", "user", "/cwd", "Billing", "plunk otp flow", "{}"),
            )
            raw.execute(
                "insert into messages_fts (rowid,text,title,cwd,source,role)"
                " select id,text,title,cwd,source,role from messages"
            )
            raw.commit()
            before = {r[0] for r in raw.execute("select name from sqlite_master where type='table'").fetchall()}
            raw.close()
            self.assertNotIn("source_refresh_state", before)

            # Open under the current schema -> simulates the v1.2.0 upgrade.
            store = ThreadStore(db)
            try:
                after = {r[0] for r in store.conn.execute("select name from sqlite_master where type='table'").fetchall()}
                self.assertIn("source_refresh_state", after)
                self.assertEqual(store.conn.execute("select count(*) from messages").fetchone()[0], 1)
                hit = store.conn.execute("select count(*) from messages_fts where messages_fts match 'plunk'").fetchone()[0]
                self.assertEqual(hit, 1)
                # The write that would raise "no such table" on an unmigrated DB now succeeds.
                self.assertFalse(store.source_freshness(["codex"])["known"])
                store.mark_sources_checked(["codex"], "2026-06-19T00:00:00+00:00")
                fr = store.source_freshness(["codex"])
                self.assertTrue(fr["known"])
                self.assertEqual(fr["per_source"]["codex"], "2026-06-19T00:00:00+00:00")
            finally:
                store.close()

if __name__ == "__main__":
    unittest.main()
