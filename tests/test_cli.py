import json
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from threadlens import cli as cli_module
from threadlens.cli import main
from threadlens.models import ThreadMessage
from threadlens.profiles import SourceProfile, save_profiles
from threadlens.store import ThreadStore


class CliTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_version_flag(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("threadlens 1.0.1", stdout.getvalue())

    def test_skill_command_prints_bundled_skill_path(self):
        code, stdout, stderr = self.run_cli(["skill"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("threadlens/skills/threadlens", stdout)
        self.assertIn("SKILL.md", stdout)

    def test_skill_command_json(self):
        code, stdout, stderr = self.run_cli(["skill", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["name"], "threadlens")
        self.assertTrue(payload["skill_md"].endswith("SKILL.md"))

    def write_codex_session(self, home: Path, *, text: str = "alpha setup phrase") -> Path:
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

    def write_empty_cursor_store(self, home: Path) -> Path:
        store_dir = home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
        store_dir.mkdir(parents=True)
        path = store_dir / "state.vscdb"
        conn = sqlite3.connect(path)
        try:
            conn.execute("create table cursorDiskKV (key text, value text)")
            conn.commit()
        finally:
            conn.close()
        return path

    def test_start_indexes_default_builtin_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            self.write_codex_session(home)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "start",
                    "--home",
                    str(home),
                ]
            )
            store = ThreadStore(db)
            try:
                stats = [dict(row) for row in store.stats()]
            finally:
                store.close()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Threadlens setup", stdout)
        self.assertIn("Detected sources:", stdout)
        self.assertIn("cursor: 0 path(s)", stdout)
        self.assertIn("Ready.", stdout)
        self.assertEqual(stats, [{"source": "codex", "messages": 1, "threads": 1}])

    def test_start_reports_partial_when_detected_source_indexes_no_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            self.write_codex_session(home)
            self.write_empty_cursor_store(home)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "start",
                    "--home",
                    str(home),
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Partially ready.", stdout)
        self.assertIn("Missing indexed sources: cursor", stdout)

    def test_start_reports_unknown_source_before_setup_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "start",
                    "--source",
                    "notreal",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "Unknown source: notreal\n")

    def test_doctor_reports_index_not_ready_when_sources_exist_but_index_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            self.write_codex_session(home)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "doctor",
                    "--home",
                    str(home),
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Sources", stdout)
        self.assertIn("codex: ok (1/1 paths with messages)", stdout)
        self.assertIn("Index", stdout)
        self.assertIn("status: not_ready", stdout)
        self.assertIn("action: run: threadlens start", stdout)

    def test_search_bootstraps_empty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            self.write_codex_session(home, text="needle phrase from first run")
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "search",
                    "--home",
                    str(home),
                    "needle",
                ]
            )

        self.assertEqual(code, 0)
        self.assertIn("Index is empty. Running first-time indexing...", stderr)
        self.assertIn("Refreshed 1 message(s)", stderr)
        self.assertIn("[1] codex codex-session", stdout)
        self.assertIn("needle", stdout)

    def test_search_no_bootstrap_fails_fast_on_empty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "search",
                    "needle",
                    "--json",
                    "--no-bootstrap",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Index is empty. Run `threadlens start`.", stderr)

    def test_search_reports_sqlite_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"
            store = ThreadStore(db)
            try:
                store.add_messages(
                    [
                        ThreadMessage(
                            source="codex",
                            thread_id="t1",
                            message_id="m1",
                            path=root / "thread.jsonl",
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="",
                            title="needle",
                            text="needle phrase",
                        )
                    ]
                )
            finally:
                store.close()

            with patch.object(cli_module.ThreadStore, "search_sessions", side_effect=sqlite3.Error("database is locked")):
                code, stdout, stderr = self.run_cli(
                    [
                        "--db",
                        str(db),
                        "--config",
                        str(config),
                        "search",
                        "needle",
                        "--no-bootstrap",
                    ]
                )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Search failed: database is locked", stderr)

    def test_sources_reports_malformed_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"
            home = root / "home"
            home.mkdir()
            config.write_text("{bad json", encoding="utf-8")

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "sources",
                    "--home",
                    str(home),
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Could not load source profile config", stderr)
        self.assertIn("invalid JSON", stderr)

    def test_sources_rejects_unsafe_raw_resume_template_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "sources",
                    "add",
                    "agent",
                    "--path",
                    "agent.jsonl",
                    "--resume-template",
                    "cd {raw_cwd} && agent resume {raw_session_id}",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("Resume template field is not supported: raw_cwd", stdout)

    def test_refresh_reports_bad_file_and_indexes_remaining_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"
            source_dir = root / "logs"
            source_dir.mkdir()
            bad = source_dir / "bad.jsonl"
            good = source_dir / "good.jsonl"
            bad.write_text("{}", encoding="utf-8")
            good.write_text("{}", encoding="utf-8")
            save_profiles({"agent": SourceProfile(name="agent", paths=[str(source_dir)])}, config)

            def fake_source_profile_messages(profile: SourceProfile, path: Path):
                if path == bad:
                    def fail_after_partial_message():
                        yield ThreadMessage(
                            source=profile.name,
                            thread_id="bad",
                            message_id="bad-1",
                            path=path,
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="",
                            title="bad",
                            text="partial bad message",
                        )
                        raise ValueError("broken parser")

                    return fail_after_partial_message()

                return iter(
                    [
                        ThreadMessage(
                            source=profile.name,
                            thread_id="good",
                            message_id="good-1",
                            path=path,
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="",
                            title="good",
                            text="indexed surviving message",
                        )
                    ]
                )

            with patch.object(cli_module, "source_profile_messages", side_effect=fake_source_profile_messages):
                code, stdout, stderr = self.run_cli(
                    [
                        "--db",
                        str(db),
                        "--config",
                        str(config),
                        "refresh",
                        "--source",
                        "agent",
                        "--force",
                    ]
                )

            store = ThreadStore(db)
            try:
                stats = [dict(row) for row in store.stats()]
            finally:
                store.close()

        self.assertEqual(code, 0)
        self.assertIn("Refreshed 1 message(s)", stdout)
        self.assertIn("agent skipped errored files: 1", stdout)
        self.assertIn("broken parser", stderr)
        self.assertEqual(stats, [{"source": "agent", "messages": 1, "threads": 1}])

    def test_refresh_skips_fts_rebuild_when_all_files_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            db = root / "index.sqlite"
            source_dir = root / "logs"
            source_dir.mkdir()
            path = source_dir / "agent.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "session": {"id": "s1"},
                        "message": {"id": "m1", "role": "user", "content": "stable content"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profile = SourceProfile(
                name="agent",
                paths=[str(source_dir)],
                session_key="session.id",
                message_key="message.id",
                role_key="message.role",
                text_key="message.content",
            )
            save_profiles({"agent": profile}, config)
            store = ThreadStore(db)
            try:
                first = cli_module.refresh_store(
                    store,
                    ["agent"],
                    {"agent": profile},
                    home=root,
                    limit_files=None,
                    force=False,
                    days=None,
                    include_paths=[],
                )

                def fail_rebuild():
                    raise AssertionError("unchanged refresh should not rebuild FTS")

                store.rebuild_fts = fail_rebuild  # type: ignore[method-assign]
                second = cli_module.refresh_store(
                    store,
                    ["agent"],
                    {"agent": profile},
                    home=root,
                    limit_files=None,
                    force=False,
                    days=None,
                    include_paths=[],
                )
            finally:
                store.close()

        self.assertTrue(first["rebuilt_fts"])
        self.assertFalse(second["rebuilt_fts"])
        self.assertEqual(second["added"], 0)
        self.assertEqual(second["skipped"]["agent"], 1)

    def test_doctor_reports_stale_index_when_new_source_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            self.write_codex_session(home, text="first indexed phrase")
            config = root / "sources.json"
            db = root / "index.sqlite"

            code, _, _ = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "refresh",
                    "--home",
                    str(home),
                    "--source",
                    "codex",
                ]
            )
            self.assertEqual(code, 0)

            later = home / ".codex" / "sessions" / "later.jsonl"
            later.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {
                            "type": "session_meta",
                            "timestamp": "2026-06-18T00:00:00Z",
                            "payload": {"id": "later-session", "cwd": "/tmp/threadlens-test"},
                        },
                        {
                            "type": "response_item",
                            "timestamp": "2026-06-18T00:01:00Z",
                            "payload": {
                                "id": "msg-user",
                                "type": "message",
                                "role": "user",
                                "content": [{"text": "later source phrase"}],
                            },
                        },
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "doctor",
                    "--home",
                    str(home),
                    "--json",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["index"]["status"], "ready")
        self.assertEqual(payload["index"]["freshness"]["status"], "stale")
        self.assertEqual(payload["index"]["freshness"]["missing_files"], 1)
        self.assertEqual(payload["index"]["freshness"]["action"], "run: threadlens refresh")

    def test_eval_accepts_multiple_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "index.sqlite"
            config = root / "sources.json"
            eval_file = root / "eval.json"
            store = ThreadStore(db)
            try:
                store.add_messages(
                    [
                        ThreadMessage(
                            source="omp",
                            thread_id="alt-session",
                            message_id="m1",
                            path=root / "omp.jsonl",
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="/tmp/project",
                            title="shared",
                            text="shared remembered topic",
                        )
                    ]
                )
            finally:
                store.close()
            eval_file.write_text(
                json.dumps(
                    [
                        {
                            "case_id": "multi",
                            "target": {"source": "codex", "session_id": "missing"},
                            "targets": [
                                {"source": "codex", "session_id": "missing"},
                                {"source": "omp", "session_id": "alt-session"},
                            ],
                            "queries": ["shared remembered topic"],
                            "negative_queries": ["unrelated phrase"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                [
                    "--db",
                    str(db),
                    "--config",
                    str(config),
                    "eval",
                    str(eval_file),
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("passed: True", stdout)
        self.assertIn("recall@5: 1/1 = 1.000", stdout)

    def test_amp_does_not_emit_unverified_resume_command(self):
        command = cli_module.resume_command_for("amp", "history-session", "/tmp/amp")

        self.assertEqual(command, "")


if __name__ == "__main__":
    unittest.main()
