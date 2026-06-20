import tempfile
import unittest
from pathlib import Path

from threadlens.models import ThreadMessage
from threadlens.store import ThreadStore


def make_message(
    *,
    source: str = "codex",
    thread_id: str = "t1",
    message_id: str = "m1",
    path: str = "/tmp/thread.jsonl",
    timestamp: str = "2026-06-17T00:00:00Z",
    cwd: str = "/tmp/project",
    title: str = "test",
    text: str = "hello world",
) -> ThreadMessage:
    return ThreadMessage(
        source=source,
        thread_id=thread_id,
        message_id=message_id,
        path=Path(path),
        line=1,
        timestamp=timestamp,
        role="user",
        cwd=cwd,
        title=title,
        text=text,
    )


class StoreIndexesTests(unittest.TestCase):
    def test_get_session_uses_source_thread_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages([
                    make_message(source="codex", thread_id="t1", message_id="m1",
                                 timestamp="2026-06-17T00:00:00Z"),
                    make_message(source="codex", thread_id="t1", message_id="m2",
                                 timestamp="2026-06-17T00:01:00Z"),
                    make_message(source="claude", thread_id="t2", message_id="m3",
                                 timestamp="2026-06-17T00:02:00Z"),
                ])
                rows = list(store.conn.execute(
                    "EXPLAIN QUERY PLAN select * from messages"
                    " where source = ? and thread_id = ? order by timestamp, id",
                    ("codex", "t1"),
                ))
                plan_text = " ".join(row["detail"] for row in rows)
                self.assertIn("USING INDEX", plan_text)
                self.assertNotIn("SCAN messages", plan_text)
                self.assertIn("idx_messages_source_thread", plan_text)
            finally:
                store.close()

    def test_delete_file_uses_source_path_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages([
                    make_message(source="codex", thread_id="t1", message_id="m1",
                                 path="/tmp/file_a.jsonl"),
                    make_message(source="codex", thread_id="t1", message_id="m2",
                                 path="/tmp/file_b.jsonl"),
                    make_message(source="claude", thread_id="t2", message_id="m3",
                                 path="/tmp/file_a.jsonl"),
                ])
                rows = list(store.conn.execute(
                    "EXPLAIN QUERY PLAN delete from messages where source = ? and path = ?",
                    ("codex", "/tmp/file_a.jsonl"),
                ))
                plan_text = " ".join(row["detail"] for row in rows)
                self.assertIn("USING INDEX", plan_text)
                self.assertNotIn("SCAN messages", plan_text)
                self.assertIn("idx_messages_source_path", plan_text)
            finally:
                store.close()

    def test_indexes_exist_in_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                rows = store.conn.execute(
                    "select name from sqlite_master where type='index' and tbl_name='messages'"
                ).fetchall()
                names = {r[0] for r in rows}
                self.assertIn("idx_messages_source_path", names)
                self.assertIn("idx_messages_source_thread", names)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
