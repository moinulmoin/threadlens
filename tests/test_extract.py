import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from threadlens.extract import amp_history_messages, agent_jsonl_messages, claude_messages, codex_messages, content_to_text, flatten_text
from threadlens.models import ThreadMessage
from threadlens.profiles import SourceProfile, load_profiles, save_profiles
from threadlens.sources import cursor_messages, opencode_messages, source_paths, source_profile_messages, source_profile_paths
from threadlens.store import ThreadStore, make_fts_query


def _write_opencode_db(db: Path) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("create table session (id text, directory text, path text, title text)")
        conn.execute("create table message (id text, session_id text, time_created integer, data text)")
        conn.execute("create table part (id text, message_id text, session_id text, time_created integer, data text)")
        conn.execute(
            "insert into session (id, directory, path, title) values (?, ?, ?, ?)",
            ("ses", "/tmp/open", "", "OpenCode Run"),
        )
        conn.execute(
            "insert into message (id, session_id, time_created, data) values (?, ?, ?, ?)",
            ("msg", "ses", 1781771840209, json.dumps({"role": "user", "time": {"created": 1781771840209}})),
        )
        conn.execute(
            "insert into part (id, message_id, session_id, time_created, data) values (?, ?, ?, ?, ?)",
            ("prt", "msg", "ses", 1781771840214, json.dumps({"type": "text", "text": "live opencode transcript text"})),
        )
        conn.commit()
    finally:
        conn.close()


class ExtractTests(unittest.TestCase):
    def test_flatten_text_skips_sensitive_keys(self):
        value = {
            "text": "real task text",
            "accessToken": "secret-token",
            "nested": {"api_key": "secret-key", "content": "visible content"},
        }

        pieces = flatten_text(value)

        self.assertIn("real task text", pieces)
        self.assertIn("visible content", pieces)
        self.assertNotIn("secret-token", pieces)
        self.assertNotIn("secret-key", pieces)

    def test_content_to_text_skips_structural_type_labels(self):
        text = content_to_text([{"type": "input_text", "text": "actual prompt"}])

        self.assertEqual(text, "actual prompt")

    def test_codex_messages_indexes_user_and_assistant_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "timestamp": "t0", "payload": {"id": "sid", "cwd": "/tmp/project"}},
                {"type": "response_item", "timestamp": "t1", "payload": {"type": "message", "role": "developer", "content": [{"text": "skip"}]}},
                {"type": "response_item", "timestamp": "t2", "payload": {"type": "message", "role": "user", "content": [{"text": "find otp bug"}]}},
                {"type": "response_item", "timestamp": "t3", "payload": {"type": "message", "role": "assistant", "content": [{"text": "fixed otp bug"}]}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            messages = list(codex_messages(path))

        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0].thread_id, "sid")
        self.assertEqual(messages[0].cwd, "/tmp/project")

    def test_claude_messages_skips_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            rows = [
                {"type": "user", "isMeta": True, "message": {"role": "user", "content": "skip"}},
                {
                    "type": "user",
                    "uuid": "u1",
                    "sessionId": "sid",
                    "timestamp": "t1",
                    "cwd": "/tmp/project",
                    "message": {"role": "user", "content": "launch video"},
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            messages = list(claude_messages(path))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].text, "launch video")

    def test_agent_jsonl_messages_indexes_visible_text_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            rows = [
                {"type": "session", "id": "pi-session", "timestamp": "t0", "cwd": "/tmp/pi-project"},
                {
                    "type": "message",
                    "id": "u1",
                    "timestamp": "2026-06-17T00:01:00Z",
                    "message": {"role": "user", "content": [{"type": "text", "text": "find pi session"}]},
                },
                {
                    "type": "message",
                    "id": "skip-tool",
                    "timestamp": "2026-06-17T00:02:00Z",
                    "message": {"role": "user", "content": [{"type": "tool_result", "content": "tool noise"}]},
                },
                {
                    "type": "message",
                    "id": "skip-role",
                    "timestamp": "2026-06-17T00:03:00Z",
                    "message": {"role": "developer", "content": [{"type": "text", "text": "developer instructions"}]},
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            messages = list(agent_jsonl_messages(path, source="pi"))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].source, "pi")
        self.assertEqual(messages[0].thread_id, "pi-session")
        self.assertEqual(messages[0].cwd, "/tmp/pi-project")
        self.assertEqual(messages[0].text, "find pi session")

    def test_agent_jsonl_messages_reads_droid_session_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "droid.jsonl"
            rows = [
                {"type": "session_start", "id": "droid-session", "title": "Droid Launch", "cwd": "/tmp/droid"},
                {
                    "type": "message",
                    "id": "a1",
                    "timestamp": "2026-06-17T00:01:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "private reasoning"},
                            {"type": "text", "text": "public droid answer"},
                        ],
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            messages = list(agent_jsonl_messages(path, source="droid"))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].source, "droid")
        self.assertEqual(messages[0].thread_id, "droid-session")
        self.assertEqual(messages[0].title, "Droid Launch")
        self.assertEqual(messages[0].text, "public droid answer")

    def test_amp_history_messages_indexes_prompt_history_by_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            rows = [
                {"text": "first amp prompt", "cwd": "/tmp/amp-project"},
                {"text": "second amp prompt", "cwd": "/tmp/amp-project"},
                {"text": "", "cwd": "/tmp/amp-project"},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            messages = list(amp_history_messages(path))

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].source, "amp")
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].cwd, "/tmp/amp-project")
        self.assertEqual(messages[0].title, "amp-project")
        self.assertEqual(messages[0].thread_id, messages[1].thread_id)
        self.assertEqual(messages[0].text, "first amp prompt")

    def test_cursor_messages_skip_internal_agent_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(path)
            try:
                conn.execute("create table cursorDiskKV (key text, value text)")
                conn.execute(
                    "insert into cursorDiskKV (key, value) values (?, ?)",
                    (
                        "agentKv:blob:system",
                        json.dumps({"role": "system", "content": "cursor system instructions"}),
                    ),
                )
                conn.execute(
                    "insert into cursorDiskKV (key, value) values (?, ?)",
                    (
                        "agentKv:blob:user",
                        json.dumps({"role": "user", "content": "internal cursor prompt payload"}),
                    ),
                )
                conn.execute(
                    "insert into cursorDiskKV (key, value) values (?, ?)",
                    (
                        "bubbleId:session-1:message-1",
                        json.dumps(
                            {
                                "bubbleId": "message-1",
                                "createdAt": "2026-06-17T00:00:00Z",
                                "text": "real cursor user message",
                            }
                        ),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            messages = list(cursor_messages(path))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].thread_id, "session-1")
        self.assertEqual(messages[0].text, "real cursor user message")

    def test_opencode_messages_reads_text_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            conn = sqlite3.connect(path)
            try:
                conn.execute("create table session (id text, directory text, path text, title text)")
                conn.execute("create table message (id text, session_id text, time_created integer, data text)")
                conn.execute("create table part (id text, message_id text, session_id text, time_created integer, data text)")
                conn.execute(
                    "insert into session (id, directory, path, title) values (?, ?, ?, ?)",
                    ("open-session", "/tmp/open", "", "OpenCode Run"),
                )
                conn.execute(
                    "insert into message (id, session_id, time_created, data) values (?, ?, ?, ?)",
                    ("m1", "open-session", 1760000000000, json.dumps({"role": "user"})),
                )
                conn.execute(
                    "insert into part (id, message_id, session_id, time_created, data) values (?, ?, ?, ?, ?)",
                    ("p1", "m1", "open-session", 1760000000000, json.dumps({"type": "text", "text": "opencode search text"})),
                )
                conn.execute(
                    "insert into part (id, message_id, session_id, time_created, data) values (?, ?, ?, ?, ?)",
                    ("p2", "m1", "open-session", 1760000000001, json.dumps({"type": "tool_result", "content": "tool noise"})),
                )
                conn.commit()
            finally:
                conn.close()

            messages = list(opencode_messages(path))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].source, "opencode")
        self.assertEqual(messages[0].thread_id, "open-session")
        self.assertEqual(messages[0].message_id, "p1")
        self.assertEqual(messages[0].cwd, "/tmp/open")
        self.assertEqual(messages[0].title, "OpenCode Run")
        self.assertEqual(messages[0].text, "opencode search text")

    def test_opencode_source_paths_detects_nonempty_local_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = home / ".local" / "share" / "opencode" / "opencode.db"
            db.parent.mkdir(parents=True)
            conn = sqlite3.connect(db)
            try:
                conn.execute("create table session (id text, directory text, path text, title text)")
                conn.execute("create table message (id text, session_id text, time_created integer, data text)")
                conn.execute("create table part (id text, message_id text, session_id text, time_created integer, data text)")
                conn.execute(
                    "insert into session (id, directory, path, title) values (?, ?, ?, ?)",
                    ("ses_live_shape", "/tmp/open", "", "OpenCode Run"),
                )
                conn.execute(
                    "insert into message (id, session_id, time_created, data) values (?, ?, ?, ?)",
                    (
                        "msg_live_shape",
                        "ses_live_shape",
                        1781771840209,
                        json.dumps(
                            {
                                "role": "user",
                                "time": {"created": 1781771840209},
                                "agent": "build",
                                "model": {"providerID": "opencode", "modelID": "deepseek-v4-flash-free"},
                            }
                        ),
                    ),
                )
                conn.execute(
                    "insert into part (id, message_id, session_id, time_created, data) values (?, ?, ?, ?, ?)",
                    (
                        "prt_live_shape",
                        "msg_live_shape",
                        "ses_live_shape",
                        1781771840214,
                        json.dumps({"type": "text", "text": "live opencode transcript text"}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            paths = source_paths("opencode", home=home, environ={})

        self.assertEqual(paths, [db])

    def test_amp_source_paths_detects_history_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            history = home / ".local" / "share" / "amp" / "history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(json.dumps({"text": "amp prompt", "cwd": "/tmp/amp"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={})

        self.assertEqual(paths, [history])

    def test_cursor_source_paths_detects_linux_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            state = home / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            state.parent.mkdir(parents=True)
            state.write_bytes(b"")

            paths = source_paths("cursor", home=home, environ={})

        self.assertEqual(paths, [state])

    def test_cursor_source_paths_detects_windows_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            state = home / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            state.parent.mkdir(parents=True)
            state.write_bytes(b"")

            paths = source_paths("cursor", home=home, environ={})

        self.assertEqual(paths, [state])

    def test_amp_source_paths_detects_windows_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            history = home / "AppData" / "Roaming" / "amp" / "history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(json.dumps({"text": "amp prompt", "cwd": "/tmp/amp"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={})

        self.assertEqual(paths, [history])

    def test_amp_source_paths_honors_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xdg = home / "custom-data"
            history = xdg / "amp" / "history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(json.dumps({"text": "amp prompt", "cwd": "/tmp/amp"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={"XDG_DATA_HOME": str(xdg)})

        self.assertEqual(paths, [history])

    def test_cursor_source_paths_honors_appdata_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            appdata = home / "custom-roaming"
            state = appdata / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            state.parent.mkdir(parents=True)
            state.write_bytes(b"")

            paths = source_paths("cursor", home=home, environ={"APPDATA": str(appdata)})

        self.assertEqual(paths, [state])

    def test_amp_source_paths_found_when_xdg_set_but_store_in_default(self):
        # XDG_DATA_HOME points elsewhere, but the agent still wrote to ~/.local/share.
        # The conventional path must remain a candidate, not be replaced.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "custom-xdg").mkdir()
            history = home / ".local" / "share" / "amp" / "history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(json.dumps({"text": "amp prompt", "cwd": "/tmp/amp"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={"XDG_DATA_HOME": str(home / "custom-xdg")})

        self.assertEqual(paths, [history])

    def test_cursor_source_paths_found_when_xdg_config_set_but_store_in_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "custom-xdg").mkdir()
            state = home / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            state.parent.mkdir(parents=True)
            state.write_bytes(b"")

            paths = source_paths("cursor", home=home, environ={"XDG_CONFIG_HOME": str(home / "custom-xdg")})

        self.assertEqual(paths, [state])

    def test_opencode_source_paths_found_when_xdg_set_but_store_in_default(self):
        # XDG_DATA_HOME points elsewhere, but OpenCode still wrote to ~/.local/share.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "custom-xdg").mkdir()
            db = home / ".local" / "share" / "opencode" / "opencode.db"
            _write_opencode_db(db)

            paths = source_paths("opencode", home=home, environ={"XDG_DATA_HOME": str(home / "custom-xdg")})

        self.assertEqual(paths, [db])

    def test_amp_source_paths_found_when_appdata_set_but_store_in_default(self):
        # APPDATA points elsewhere, but amp still wrote to the conventional AppData/Roaming.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            history = home / "AppData" / "Roaming" / "amp" / "history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(json.dumps({"text": "amp prompt", "cwd": "/tmp/amp"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={"APPDATA": str(home / "custom-roaming")})

        self.assertEqual(paths, [history])

    def test_amp_source_paths_returns_both_xdg_and_default_stores(self):
        # Sessions in BOTH $XDG_DATA_HOME/amp and conventional ~/.local/share/amp must both be found.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xdg = home / "custom-xdg"
            xdg_history = xdg / "amp" / "history.jsonl"
            xdg_history.parent.mkdir(parents=True)
            xdg_history.write_text(json.dumps({"text": "xdg amp", "cwd": "/tmp/x"}) + "\n", encoding="utf-8")
            default_history = home / ".local" / "share" / "amp" / "history.jsonl"
            default_history.parent.mkdir(parents=True)
            default_history.write_text(json.dumps({"text": "default amp", "cwd": "/tmp/d"}) + "\n", encoding="utf-8")

            paths = source_paths("amp", home=home, environ={"XDG_DATA_HOME": str(xdg)})

        self.assertEqual(paths, [xdg_history, default_history])

    def test_opencode_source_paths_returns_both_xdg_and_default_dbs(self):
        # Databases in BOTH $XDG_DATA_HOME/opencode and conventional ~/.local/share/opencode must both be found.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xdg = home / "custom-xdg"
            xdg_db = xdg / "opencode" / "opencode.db"
            _write_opencode_db(xdg_db)
            default_db = home / ".local" / "share" / "opencode" / "opencode.db"
            _write_opencode_db(default_db)

            paths = source_paths("opencode", home=home, environ={"XDG_DATA_HOME": str(xdg)})

        self.assertEqual(paths, [xdg_db, default_db])

    def test_store_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages(
                    [
                        ThreadMessage(
                            source="codex",
                            thread_id="t1",
                            message_id="m1",
                            path=Path("/tmp/thread.jsonl"),
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="/tmp/project",
                            title="otp",
                            text="debug plunk otp delivery",
                        )
                    ]
                )

                rows = store.search("plunk otp")
            finally:
                store.close()

        self.assertEqual(len(rows), 1)

    def test_store_search_sessions_groups_by_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages(
                    [
                        ThreadMessage(
                            source="codex",
                            thread_id="t1",
                            message_id="m1",
                            path=Path("/tmp/thread.jsonl"),
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="/tmp/project",
                            title="otp",
                            text="debug plunk otp delivery",
                        ),
                        ThreadMessage(
                            source="codex",
                            thread_id="t1",
                            message_id="m2",
                            path=Path("/tmp/thread.jsonl"),
                            line=2,
                            timestamp="2026-06-17T00:01:00Z",
                            role="assistant",
                            cwd="/tmp/project",
                            title="otp",
                            text="fixed plunk otp issue",
                        ),
                    ]
                )

                results = store.search_sessions("plunk otp")
            finally:
                store.close()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["result_id"], "codex:t1")
        self.assertEqual(len(results[0]["best_snippets"]), 2)

    def test_store_search_sessions_prefix_and_fuzzy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages(
                    [
                        ThreadMessage(
                            source="claude",
                            thread_id="t2",
                            message_id="m1",
                            path=Path("/tmp/thread.jsonl"),
                            line=1,
                            timestamp="2026-06-17T00:00:00Z",
                            role="user",
                            cwd="/tmp/project",
                            title="review",
                            text="review the rider modal changes",
                        )
                    ]
                )

                prefix = store.search_sessions("revie")
                fuzzy = store.search_sessions("rveiw")
            finally:
                store.close()

        self.assertEqual(prefix[0]["result_id"], "claude:t2")
        self.assertEqual(fuzzy[0]["result_id"], "claude:t2")

    def test_store_tracks_indexed_file_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thread.jsonl"
            path.write_text("{}", encoding="utf-8")
            stat = path.stat()
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                self.assertFalse(
                    store.file_is_current(
                        "codex",
                        path,
                        mtime_ns=stat.st_mtime_ns,
                        size=stat.st_size,
                    )
                )
                store.mark_file_indexed(
                    "codex",
                    path,
                    mtime_ns=stat.st_mtime_ns,
                    size=stat.st_size,
                    message_count=0,
                )
                self.assertTrue(
                    store.file_is_current(
                        "codex",
                        path,
                        mtime_ns=stat.st_mtime_ns,
                        size=stat.st_size,
                    )
                )
            finally:
                store.close()

    def test_make_fts_query_sanitizes_punctuation(self):
        self.assertEqual(make_fts_query("plunk, otp!"), "plunk AND otp")

    def test_source_profile_messages_maps_jsonl_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent.jsonl"
            rows = [
                {
                    "session": {"id": "s1"},
                    "message": {"id": "m1", "role": "user", "content": "debug custom agent search"},
                    "created": "2026-06-17T00:00:00Z",
                    "workspace": {"cwd": "/tmp/custom"},
                    "title": "custom run",
                }
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            profile = SourceProfile(
                name="aider",
                paths=[str(path)],
                session_key="session.id",
                message_key="message.id",
                role_key="message.role",
                text_key="message.content",
                timestamp_key="created",
                cwd_key="workspace.cwd",
                title_key="title",
            )

            messages = list(source_profile_messages(profile, path))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].source, "aider")
        self.assertEqual(messages[0].thread_id, "s1")
        self.assertEqual(messages[0].message_id, "m1")
        self.assertEqual(messages[0].cwd, "/tmp/custom")
        self.assertEqual(messages[0].text, "debug custom agent search")

    def test_source_profile_paths_supports_directories_and_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "sources.json"
            nested = root / "logs"
            nested.mkdir()
            path = nested / "agent.jsonl"
            path.write_text("{}", encoding="utf-8")
            profile = SourceProfile(name="agentx", paths=[str(nested)])

            save_profiles({"agentx": profile}, config)
            loaded = load_profiles(config)

            self.assertEqual(loaded["agentx"].name, "agentx")
            self.assertEqual(source_profile_paths(loaded["agentx"]), [path])


if __name__ == "__main__":
    unittest.main()
