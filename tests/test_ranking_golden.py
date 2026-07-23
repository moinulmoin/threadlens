"""
Ranking characterization (golden) tests for threadlens.store.search_sessions.

These tests pin the CURRENT output of the ranking pipeline byte-for-byte so
that any regression in score composition, dedupe, snippet selection, or sort
order fails loudly.  They are NOT correctness tests — if a value looks odd,
record it as-is and fix it in a separate, gated plan.

Determinism contract
--------------------
* TZ is forced to "UTC" in setUp / restored in tearDown so that
  recency_boost's time.mktime call is timezone-independent.
* threadlens.store.time.time is patched to FROZEN_TIME in every test so
  that age_days is identical regardless of when/where the suite runs.

Corpus design
-------------
One shared store exercises six scenarios:
  MM  multi-message grouping    — codex/auth-session (2 unique msgs)
  DD  duplicate message_id dedupe — auth-1 inserted at line=1 and line=2
  EX  exact FTS stage            — "authentication token" both exact
  PX  prefix FTS stage           — "authent token" → authent* matches
  FZ  fuzzy fallback             — "kubernets" typo → fuzzy match
  CS  coverage-vs-score ordering — 2-token sessions beat 1-token despite age
  CW  cwd-prefix filter          — only /work/deploy subtree returned
  RT  recency near-tie           — recent-b (09:01) vs recent-a (09:00)

Expected literals were captured by running this file once with temporary
print(json.dumps(...)) calls and pasting the output verbatim, then removing
the print calls.  Do NOT edit expected values without a matching store change.
"""

import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from threadlens.models import ThreadMessage
from threadlens.store import ThreadStore

# Frozen wall-clock: 2024-07-01T00:00:00Z  (= 1719792000 UTC).
# All corpus timestamps are strictly before this epoch.
FROZEN_TIME = 1719792000.0

_FAKE_PATH = Path("/tmp/thread.jsonl")


def _msg(
    *,
    source: str = "codex",
    thread_id: str,
    message_id: str,
    timestamp: str,
    role: str = "user",
    cwd: str = "/work/project",
    title: str = "session",
    text: str,
    line: int = 1,
) -> ThreadMessage:
    return ThreadMessage(
        source=source,
        thread_id=thread_id,
        message_id=message_id,
        path=_FAKE_PATH,
        line=line,
        timestamp=timestamp,
        role=role,
        cwd=cwd,
        title=title,
        text=text,
    )


# ---------------------------------------------------------------------------
# Fixed corpus (all scenarios in one store)
# ---------------------------------------------------------------------------
CORPUS: list[ThreadMessage] = [
    # [MM, EX] codex/auth-session — 2 unique messages, both match "authentication token"
    _msg(
        source="codex",
        thread_id="auth-session",
        message_id="auth-1",
        timestamp="2024-06-20T10:00:00Z",
        role="user",
        cwd="/work/auth",
        title="authentication debug",
        text="debug authentication token validation",
    ),
    _msg(
        source="codex",
        thread_id="auth-session",
        message_id="auth-2",
        timestamp="2024-06-20T10:05:00Z",
        role="assistant",
        cwd="/work/auth",
        title="authentication debug",
        text="the authentication flow uses JWT tokens for session management",
    ),
    # [DD] Same message_id "auth-1" but line=2 → different doc_key → separate DB row.
    #      group_candidate_sessions dedupes by (source, thread_id, message_id).
    #      This line=2 row has timestamp 10:06 > 10:00, so FTS ORDER BY timestamp DESC
    #      returns it BEFORE line=1 — meaning line=2 wins the dedup race and line=1
    #      is silently skipped.  The test_duplicate_message_id_dedupe case pins this.
    _msg(
        source="codex",
        thread_id="auth-session",
        message_id="auth-1",
        timestamp="2024-06-20T10:06:00Z",
        role="user",
        cwd="/work/auth",
        title="authentication debug",
        text="token authentication refresh duplicate",
        line=2,
    ),
    # [MM] codex/deploy-session — 2 messages about kubernetes deployment
    _msg(
        source="codex",
        thread_id="deploy-session",
        message_id="deploy-1",
        timestamp="2024-04-01T08:00:00Z",
        role="user",
        cwd="/work/deploy",
        title="deployment",
        text="deploy kubernetes cluster configuration",
    ),
    _msg(
        source="codex",
        thread_id="deploy-session",
        message_id="deploy-2",
        timestamp="2024-04-01T08:10:00Z",
        role="assistant",
        cwd="/work/deploy",
        title="deployment",
        text="kubernetes deployment pipeline setup complete",
    ),
    # [CS] claude/review-session — moderate recency, only "authentication" (1-token coverage)
    _msg(
        source="claude",
        thread_id="review-session",
        message_id="review-1",
        timestamp="2024-06-01T12:00:00Z",
        role="user",
        cwd="/work/review",
        title="code review",
        text="review authentication module changes pull request",
    ),
    # [RT] codex/recent-a — 60-second older of two near-identical recent sessions
    _msg(
        source="codex",
        thread_id="recent-a",
        message_id="recent-a-1",
        timestamp="2024-06-28T09:00:00Z",
        role="user",
        cwd="/work/recent",
        title="config update",
        text="update configuration settings and parameters",
    ),
    # [RT] codex/recent-b — 60 seconds newer; scores fractionally higher on recency_boost
    _msg(
        source="codex",
        thread_id="recent-b",
        message_id="recent-b-1",
        timestamp="2024-06-28T09:01:00Z",
        role="user",
        cwd="/work/recent",
        title="config update",
        text="update configuration settings and parameters",
    ),
    # [CS] codex/coverage-high — old (recency_boost=0) but both query tokens present →
    #      full coverage (2) beats partial-coverage newer session in sort order
    _msg(
        source="codex",
        thread_id="coverage-high",
        message_id="cov-1",
        timestamp="2024-03-01T00:00:00Z",
        role="user",
        cwd="/work/coverage",
        title="coverage test",
        text="authentication token refresh process complete",
    ),
    # [FZ] claude/fuzzy-session — "kubernets" typo → fuzzy fallback matches "kubernetes"
    _msg(
        source="claude",
        thread_id="fuzzy-session",
        message_id="fuzzy-1",
        timestamp="2024-06-15T00:00:00Z",
        role="user",
        cwd="/work/fuzzy",
        title="kubernetes ops",
        text="kubernetes orchestration platform deployment",
    ),
    # [CW] codex/cwd-filter-in — inside /work/deploy subtree (included by filter)
    _msg(
        source="codex",
        thread_id="cwd-filter-in",
        message_id="cwd-in-1",
        timestamp="2024-06-10T09:00:00Z",
        role="user",
        cwd="/work/deploy/app",
        title="app deploy",
        text="cluster deployment configuration finalized",
    ),
    # [CW] codex/cwd-filter-out — outside /work/deploy subtree (excluded by filter)
    _msg(
        source="codex",
        thread_id="cwd-filter-out",
        message_id="cwd-out-1",
        timestamp="2024-06-10T09:00:00Z",
        role="user",
        cwd="/work/other",
        title="other work",
        text="cluster deployment configuration finalized",
    ),
    # [PX] claude/prefix-session — "authent*" prefix matches "authentication" here
    _msg(
        source="claude",
        thread_id="prefix-session",
        message_id="prefix-1",
        timestamp="2024-05-15T09:00:00Z",
        role="user",
        cwd="/work/prefix",
        title="prefix test",
        text="the authentication and authorization setup",
    ),
]


# ---------------------------------------------------------------------------
# Normalizer — strips fields irrelevant to ranking (source_path, source_line,
# thread_id, last_timestamp, cwd, title, result_id, actions) so each golden
# assertion stays compact while covering score + order + snippet content.
# ---------------------------------------------------------------------------

def _fmt(result: dict) -> dict:
    return {
        "result_id": result["result_id"],
        "source": result["source"],
        "session_id": result["session_id"],
        "score": round(result["score"], 6),
        "matched_terms": list(result["matched_terms"]),
        "best_snippets": [
            {
                "role": s["role"],
                "timestamp": s["timestamp"],
                "snippet": s["snippet"],
                "match_type": s["match_type"],
                "score": round(s["score"], 6),
            }
            for s in result["best_snippets"]
        ],
    }


# ---------------------------------------------------------------------------
# Golden expectations (captured once from live output; do not edit without a
# matching intentional change to store.py ranking code)
# ---------------------------------------------------------------------------

# Query: "authentication token"  (used by tests: multi_message, duplicate_dedupe,
#         exact_stage, coverage_vs_score)
_AUTHENTICATION_TOKEN = [
    {
        "result_id": "codex:auth-session",
        "source": "codex",
        "session_id": "auth-session",
        "score": 154.6244,
        "matched_terms": ["authentication", "token"],
        "best_snippets": [
            # auth-1@line2 wins the dedup race (later timestamp → appears first in
            # FTS results ordered by timestamp DESC); auth-1@line1 is silently skipped.
            {
                "role": "user",
                "timestamp": "2024-06-20T10:06:00Z",
                "snippet": "[token] [authentication] refresh duplicate",
                "match_type": "exact",
                "score": 129.9244,
            },
            # auth-2 added at prefix stage (has "tokens" which matches "token*")
            {
                "role": "assistant",
                "timestamp": "2024-06-20T10:05:00Z",
                "snippet": "the [authentication] flow uses JWT [tokens] for session management",
                "match_type": "prefix",
                "score": 101.3625,
            },
        ],
    },
    {
        "result_id": "codex:coverage-high",
        "source": "codex",
        "session_id": "coverage-high",
        "score": 148.5227,
        "matched_terms": ["authentication", "token"],
        "best_snippets": [
            # Old session (2024-03-01, recency_boost=0) but full 2-token coverage keeps
            # it above all 1-token sessions in the sort by (coverage, score).
            {
                "role": "user",
                "timestamp": "2024-03-01T00:00:00Z",
                "snippet": "[authentication] [token] refresh process complete",
                "match_type": "exact",
                "score": 124.1727,
            },
        ],
    },
    {
        "result_id": "claude:review-session",
        "source": "claude",
        "session_id": "review-session",
        "score": 73.9285,
        "matched_terms": ["authentication"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-01T12:00:00Z",
                "snippet": "review [authentication] module changes pull request",
                "match_type": "any",
                "score": 61.5785,
            },
        ],
    },
    {
        "result_id": "claude:prefix-session",
        "source": "claude",
        "session_id": "prefix-session",
        "score": 72.731,
        "matched_terms": ["authentication"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-05-15T09:00:00Z",
                "snippet": "the [authentication] and authorization setup",
                "match_type": "any",
                "score": 60.381,
            },
        ],
    },
]

# Query: "authent token"  (prefix stage: authent* → authentication)
_AUTHENT_TOKEN = [
    {
        "result_id": "codex:auth-session",
        "source": "codex",
        "session_id": "auth-session",
        "score": 132.8095,
        "matched_terms": ["authent", "token"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-20T10:06:00Z",
                "snippet": "[token] [authentication] refresh duplicate",
                "match_type": "prefix",
                "score": 108.1095,
            },
            {
                "role": "assistant",
                "timestamp": "2024-06-20T10:05:00Z",
                "snippet": "the [authentication] flow uses JWT [tokens] for session management",
                "match_type": "prefix",
                "score": 101.3625,
            },
        ],
    },
    {
        "result_id": "codex:coverage-high",
        "source": "codex",
        "session_id": "coverage-high",
        "score": 126.7759,
        "matched_terms": ["authent", "token"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-03-01T00:00:00Z",
                "snippet": "[authentication] [token] refresh process complete",
                "match_type": "prefix",
                "score": 102.4259,
            },
        ],
    },
]

# Query: "kubernets"  (fuzzy fallback: typo for "kubernetes")
_KUBERNETS_FUZZY = [
    {
        "result_id": "claude:fuzzy-session",
        "source": "claude",
        "session_id": "fuzzy-session",
        "score": 74.2071,
        "matched_terms": ["kubernets"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-15T00:00:00Z",
                "snippet": "kubernetes orchestration platform deployment",
                "match_type": "fuzzy",
                "score": 61.8571,
            },
        ],
    },
    {
        "result_id": "codex:deploy-session",
        "source": "codex",
        "session_id": "deploy-session",
        "score": 69.2243,
        "matched_terms": ["kubernets"],
        "best_snippets": [
            {
                "role": "assistant",
                "timestamp": "2024-04-01T08:10:00Z",
                "snippet": "kubernetes deployment pipeline setup complete",
                "match_type": "fuzzy",
                "score": 56.5243,
            },
            {
                "role": "user",
                "timestamp": "2024-04-01T08:00:00Z",
                "snippet": "deploy kubernetes cluster configuration",
                "match_type": "fuzzy",
                "score": 56.5238,
            },
        ],
    },
]

# Query: "cluster deployment"  cwd_prefix="/work/deploy"
_CLUSTER_DEPLOYMENT_CWD = [
    {
        "result_id": "codex:cwd-filter-in",
        "source": "codex",
        "session_id": "cwd-filter-in",
        "score": 156.5022,
        "matched_terms": ["cluster", "deployment"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-10T09:00:00Z",
                "snippet": "[cluster] [deployment] configuration finalized",
                "match_type": "exact",
                "score": 132.1522,
            },
        ],
    },
    {
        "result_id": "codex:deploy-session",
        "source": "codex",
        "session_id": "deploy-session",
        "score": 138.4675,
        "matched_terms": ["cluster", "deployment"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-04-01T08:00:00Z",
                "snippet": "deploy kubernetes [cluster] configuration",
                "match_type": "exact",
                "score": 113.7675,
            },
            {
                "role": "assistant",
                "timestamp": "2024-04-01T08:10:00Z",
                "snippet": "kubernetes [deployment] pipeline setup complete",
                "match_type": "any",
                "score": 63.5843,
            },
        ],
    },
]

# Query: "configuration settings"  (recency near-tie)
_CONFIGURATION_SETTINGS = [
    # recent-b (09:01) vs recent-a (09:00): recency difference rounds to same 4-dp score
    # (159.9128), but FTS ORDER BY timestamp DESC returns recent-b first; Python's stable
    # sort preserves that order → recent-b consistently precedes recent-a.
    {
        "result_id": "codex:recent-b",
        "source": "codex",
        "session_id": "recent-b",
        "score": 159.9128,
        "matched_terms": ["configuration", "settings"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-28T09:01:00Z",
                "snippet": "update [configuration] [settings] and parameters",
                "match_type": "exact",
                "score": 135.5628,
            },
        ],
    },
    {
        "result_id": "codex:recent-a",
        "source": "codex",
        "session_id": "recent-a",
        "score": 159.9128,
        "matched_terms": ["configuration", "settings"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-28T09:00:00Z",
                "snippet": "update [configuration] [settings] and parameters",
                "match_type": "exact",
                "score": 135.5628,
            },
        ],
    },
    {
        "result_id": "codex:cwd-filter-out",
        "source": "codex",
        "session_id": "cwd-filter-out",
        "score": 76.1251,
        "matched_terms": ["configuration"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-10T09:00:00Z",
                "snippet": "cluster deployment [configuration] finalized",
                "match_type": "any",
                "score": 63.7751,
            },
        ],
    },
    {
        "result_id": "codex:cwd-filter-in",
        "source": "codex",
        "session_id": "cwd-filter-in",
        "score": 76.0408,
        "matched_terms": ["configuration"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-06-10T09:00:00Z",
                "snippet": "cluster deployment [configuration] finalized",
                "match_type": "any",
                "score": 63.6908,
            },
        ],
    },
    {
        "result_id": "codex:deploy-session",
        "source": "codex",
        "session_id": "deploy-session",
        "score": 71.2133,
        "matched_terms": ["configuration"],
        "best_snippets": [
            {
                "role": "user",
                "timestamp": "2024-04-01T08:00:00Z",
                "snippet": "deploy kubernetes cluster [configuration]",
                "match_type": "any",
                "score": 58.8633,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class RankingGoldenTests(unittest.TestCase):
    """Golden (snapshot) tests for search_sessions ranking output.

    Each test asserts the FULL ordered result list to catch regressions in
    score composition, deduplication, snippet selection, and sort order.
    """

    _prev_tz: str | None
    _store: ThreadStore
    _tmp: tempfile.TemporaryDirectory  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Fixture
    # ------------------------------------------------------------------

    def setUp(self) -> None:
        # Pin timezone to UTC so time.mktime in recency_boost is reproducible.
        self._prev_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()

        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "index.sqlite"
        self._store = ThreadStore(db_path)
        self._store.add_messages(CORPUS)

    def tearDown(self) -> None:
        self._store.close()
        self._tmp.cleanup()
        if self._prev_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._prev_tz
        time.tzset()

    def _search(
        self,
        query: str,
        *,
        limit: int = 10,
        cwd_prefix: str | None = None,
    ) -> list[dict]:
        """Run search_sessions with a frozen wall clock."""
        with unittest.mock.patch("threadlens.store.time.time", return_value=FROZEN_TIME):
            return self._store.search_sessions(query, limit=limit, cwd_prefix=cwd_prefix)

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_multi_message_grouping(self) -> None:
        """Multi-message sessions group into one result; snippet count reflects unique messages.

        auth-session has 3 DB rows (auth-1@line1, auth-1@line2, auth-2) but only 2 unique
        message_ids after dedupe (auth-1 + auth-2), so best_snippets has exactly 2 entries.
        """
        results = self._search("authentication token")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _AUTHENTICATION_TOKEN)

        # auth-session specifically: 2 snippets, not 3
        auth = got[0]
        self.assertEqual(auth["result_id"], "codex:auth-session")
        self.assertEqual(len(auth["best_snippets"]), 2)

    def test_duplicate_message_id_dedupe(self) -> None:
        """The later-timestamp auth-1@line2 row wins the dedup race; auth-1@line1 is skipped.

        Both rows share message_id="auth-1".  FTS ORDER BY rank, timestamp DESC returns the
        line=2 row (timestamp 10:06) before the line=1 row (timestamp 10:00).
        group_candidate_sessions adds auth-1@line2 to seen_messages first and silently
        skips auth-1@line1.  The snapshot pins this ordering.
        """
        results = self._search("authentication token")
        auth = _fmt(next(r for r in results if r["result_id"] == "codex:auth-session"))

        # The winning dedup entry is the line=2 duplicate (later timestamp, appears first)
        top = auth["best_snippets"][0]
        self.assertEqual(top["timestamp"], "2024-06-20T10:06:00Z")
        self.assertEqual(top["snippet"], "[token] [authentication] refresh duplicate")
        self.assertEqual(top["match_type"], "exact")

        # auth-1@line1 ("debug authentication token validation") must NOT appear
        all_snippets = [s["snippet"] for s in auth["best_snippets"]]
        self.assertNotIn("debug [authentication] [token] validation", all_snippets)

        # Full golden for auth-session
        self.assertEqual(auth, _AUTHENTICATION_TOKEN[0])

    def test_exact_stage_match(self) -> None:
        """'authentication token' triggers exact FTS stage (both words present verbatim).

        The top snippet for auth-session carries match_type='exact', confirming the exact
        AND stage fired.  The full result list is asserted byte-for-byte.
        """
        results = self._search("authentication token")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _AUTHENTICATION_TOKEN)

        # Top result, top snippet must be from exact stage
        top_snippet = got[0]["best_snippets"][0]
        self.assertEqual(top_snippet["match_type"], "exact")

    def test_prefix_stage_match(self) -> None:
        """'authent token' skips exact (no exact 'authent' word) and resolves at prefix stage.

        'authent*' matches 'authentication' → both sessions with that word appear with
        match_type='prefix'.  Sessions without 'token' are excluded (AND semantics).
        """
        results = self._search("authent token")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _AUTHENT_TOKEN)

        # All snippets should be from prefix stage
        for session in got:
            for snippet in session["best_snippets"]:
                self.assertEqual(snippet["match_type"], "prefix",
                                 f"expected prefix stage for {session['result_id']}")

    def test_fuzzy_fallback(self) -> None:
        """'kubernets' (typo) finds no FTS matches, triggering the fuzzy fallback path.

        Levenshtein distance 1 from 'kubernetes' → both fuzzy-session and deploy-session
        surface.  All snippets carry match_type='fuzzy'.
        """
        results = self._search("kubernets")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _KUBERNETS_FUZZY)

        # Every snippet must come from the fuzzy path
        for session in got:
            for snippet in session["best_snippets"]:
                self.assertEqual(snippet["match_type"], "fuzzy",
                                 f"unexpected non-fuzzy snippet in {session['result_id']}")

    def test_cwd_filter(self) -> None:
        """cwd_prefix=/work/deploy returns only sessions whose cwd is inside that subtree.

        cwd-filter-out (/work/other) must be absent; cwd-filter-in (/work/deploy/app) and
        deploy-session (/work/deploy) must be present in that order.
        """
        results = self._search("cluster deployment", cwd_prefix="/work/deploy")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _CLUSTER_DEPLOYMENT_CWD)

        result_ids = [r["result_id"] for r in got]
        self.assertIn("codex:cwd-filter-in", result_ids)
        self.assertIn("codex:deploy-session", result_ids)
        self.assertNotIn("codex:cwd-filter-out", result_ids)

    def test_recency_near_tie(self) -> None:
        """recent-b (09:01) and recent-a (09:00) have a 60-second gap.

        The tiny recency difference rounds to the same 4-decimal score (159.9128).
        Ordering is therefore determined by the FTS ORDER BY timestamp DESC propagating
        through the stable Python sort: recent-b consistently appears first.
        """
        results = self._search("configuration settings")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _CONFIGURATION_SETTINGS)

        # Both sessions present with identical rounded scores
        ids = [r["result_id"] for r in got]
        self.assertIn("codex:recent-b", ids)
        self.assertIn("codex:recent-a", ids)
        b_idx = ids.index("codex:recent-b")
        a_idx = ids.index("codex:recent-a")
        self.assertLess(b_idx, a_idx, "recent-b (newer) must rank before recent-a")

        # Confirm scores are identical at 4 decimal places
        b_score = next(r["score"] for r in got if r["result_id"] == "codex:recent-b")
        a_score = next(r["score"] for r in got if r["result_id"] == "codex:recent-a")
        self.assertEqual(b_score, a_score)

    def test_coverage_vs_score_ordering(self) -> None:
        """Sessions matching all query tokens outrank partial-coverage sessions.

        auth-session (coverage=2) and coverage-high (coverage=2) both precede review-session
        and prefix-session (coverage=1), even though coverage-high has zero recency boost
        (timestamp 2024-03-01) and lower absolute score than review-session would have alone.
        The sort key is (token_coverage, score) descending — coverage is primary.
        """
        results = self._search("authentication token")
        got = [_fmt(r) for r in results]
        self.assertEqual(got, _AUTHENTICATION_TOKEN)

        # Partition by coverage
        full = [r for r in got if len(r["matched_terms"]) == 2]
        partial = [r for r in got if len(r["matched_terms"]) == 1]
        self.assertTrue(full, "expected at least one full-coverage result")
        self.assertTrue(partial, "expected at least one partial-coverage result")

        # Every full-coverage result must appear before every partial-coverage result
        full_ids = {r["result_id"] for r in full}
        partial_ids = {r["result_id"] for r in partial}
        ids = [r["result_id"] for r in got]
        last_full_idx = max(ids.index(i) for i in full_ids)
        first_partial_idx = min(ids.index(i) for i in partial_ids)
        self.assertLess(
            last_full_idx,
            first_partial_idx,
            "all full-coverage results must precede all partial-coverage results",
        )

    def test_score_determinism(self) -> None:
        """Running all queries twice back-to-back must yield byte-identical results.

        This is a process-level guard that would catch any remaining nondeterminism
        (e.g., hash-map ordering, floating-point platform differences, uninitialized
        SQLite state) that survived the TZ + time.time patch.
        """
        queries = [
            ("authentication token", {}),
            ("authent token", {}),
            ("kubernets", {}),
            ("cluster deployment", {"cwd_prefix": "/work/deploy"}),
            ("configuration settings", {}),
        ]
        for query, kwargs in queries:
            first = [_fmt(r) for r in self._search(query, **kwargs)]
            second = [_fmt(r) for r in self._search(query, **kwargs)]
            self.assertEqual(
                first,
                second,
                f"non-deterministic output for query {query!r}",
            )


if __name__ == "__main__":
    unittest.main()
