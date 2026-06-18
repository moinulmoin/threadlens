import tempfile
import unittest
from pathlib import Path
from typing import Any

from threadlens.models import ThreadMessage
from threadlens.store import ThreadStore


def make_message(
    *,
    source: str = "codex",
    thread_id: str = "t1",
    message_id: str = "m1",
    timestamp: str = "2026-06-17T00:00:00Z",
    cwd: str = "/tmp/project",
    title: str = "search",
    text: str,
) -> ThreadMessage:
    return ThreadMessage(
        source=source,
        thread_id=thread_id,
        message_id=message_id,
        path=Path("/tmp/thread.jsonl"),
        line=1,
        timestamp=timestamp,
        role="user",
        cwd=cwd,
        title=title,
        text=text,
    )


def make_candidate(
    *,
    source: str,
    thread_id: str,
    matched_terms: list[str],
    score: float,
    stage: str,
) -> dict[str, Any]:
    return {
        "row": {
            "source": source,
            "thread_id": thread_id,
            "message_id": "m1",
            "path": "/tmp/thread.jsonl",
            "line": 1,
            "timestamp": "2026-06-17T00:00:00Z",
            "role": "user",
            "cwd": "/tmp/project",
            "title": "search",
            "text": " ".join(matched_terms),
        },
        "snippet": " ".join(matched_terms),
        "score": score,
        "stage": stage,
        "matched_terms": matched_terms,
    }


class SearchTests(unittest.TestCase):
    def test_partial_exact_match_continues_to_stronger_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                calls = []

                def fake_search(
                    fts_query: str,
                    tokens: list[str],
                    *,
                    source: str | None,
                    cwd_prefix: str | None,
                    stage: str,
                    base_score: float,
                    limit: int,
                ) -> list[dict[str, Any]]:
                    calls.append(stage)
                    if stage == "exact":
                        return [
                            make_candidate(
                                source="codex",
                                thread_id="partial",
                                matched_terms=["plunk"],
                                score=200.0,
                                stage=stage,
                            )
                        ]
                    if stage == "any":
                        return [
                            make_candidate(
                                source="claude",
                                thread_id="fallback",
                                matched_terms=["plunk", "otp"],
                                score=80.0,
                                stage=stage,
                            )
                        ]
                    return []

                def fail_fuzzy(
                    tokens: list[str],
                    *,
                    source: str | None,
                    cwd_prefix: str | None,
                    limit: int,
                ) -> list[dict[str, Any]]:
                    raise AssertionError("fuzzy fallback should not be needed after a strong any match")

                store._search_message_candidates = fake_search  # type: ignore[method-assign]
                store._fuzzy_message_candidates = fail_fuzzy  # type: ignore[method-assign]

                results = store.search_sessions("plunk otp", limit=1)
            finally:
                store.close()

        self.assertEqual(calls, ["exact", "prefix", "any"])
        self.assertEqual(results[0]["result_id"], "claude:fallback")
        self.assertEqual(results[0]["matched_terms"], ["otp", "plunk"])

    def test_fuzzy_typo_search_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages(
                    [
                        make_message(
                            source="claude",
                            thread_id="typo-target",
                            title="review",
                            text="review the rider modal changes",
                        )
                    ]
                )

                results = store.search_sessions("rveiw", limit=5)
            finally:
                store.close()

        self.assertEqual(results[0]["result_id"], "claude:typo-target")
        self.assertEqual(results[0]["best_snippets"][0]["match_type"], "fuzzy")

    def test_fuzzy_typo_search_can_find_older_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                messages = [
                    make_message(
                        source="claude",
                        thread_id="old-target",
                        message_id="old",
                        timestamp="2020-01-01T00:00:00Z",
                        title="review",
                        text="review the rider modal changes",
                    )
                ]
                for index in range(150):
                    messages.append(
                        make_message(
                            thread_id=f"new-{index}",
                            message_id=f"new-{index}",
                            timestamp=f"2026-06-17T00:{index % 60:02d}:00Z",
                            title="noise",
                            text="unrelated content",
                        )
                    )
                store.add_messages(messages)

                results = store.search_sessions("rveiw", limit=5)
            finally:
                store.close()

        self.assertEqual(results[0]["result_id"], "claude:old-target")

    def test_strong_exact_match_returns_before_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                store.add_messages(
                    [
                        make_message(
                            thread_id="exact-target",
                            title="otp",
                            text="debug plunk otp delivery",
                        )
                    ]
                )

                calls = []
                original_search = store._search_message_candidates

                def tracked_search(
                    fts_query: str,
                    tokens: list[str],
                    *,
                    source: str | None,
                    cwd_prefix: str | None,
                    stage: str,
                    base_score: float,
                    limit: int,
                ) -> list[dict[str, Any]]:
                    calls.append(stage)
                    return original_search(
                        fts_query,
                        tokens,
                        source=source,
                        cwd_prefix=cwd_prefix,
                        stage=stage,
                        base_score=base_score,
                        limit=limit,
                    )

                def fail_fuzzy(
                    tokens: list[str],
                    *,
                    source: str | None,
                    cwd_prefix: str | None,
                    limit: int,
                ) -> list[dict[str, Any]]:
                    raise AssertionError("fuzzy fallback should not run for a strong exact match")

                store._search_message_candidates = tracked_search  # type: ignore[method-assign]
                store._fuzzy_message_candidates = fail_fuzzy  # type: ignore[method-assign]

                results = store.search_sessions("plunk otp", limit=1)
            finally:
                store.close()

        self.assertEqual(calls, ["exact"])
        self.assertEqual(results[0]["result_id"], "codex:exact-target")

    def test_cwd_filter_limits_results_to_project_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ThreadStore(Path(tmp) / "index.sqlite")
            try:
                messages = [
                    make_message(
                        thread_id="target",
                        message_id="target",
                        cwd="/tmp/project/app",
                        text="debug plunk otp delivery",
                    ),
                    make_message(
                        thread_id="other",
                        message_id="other",
                        cwd="/tmp/other",
                        text="debug plunk otp delivery",
                    ),
                ]
                store.add_messages(messages)

                results = store.search_sessions("plunk otp", cwd_prefix="/tmp/project", limit=10)
            finally:
                store.close()

        self.assertEqual([result["result_id"] for result in results], ["codex:target"])


if __name__ == "__main__":
    unittest.main()
