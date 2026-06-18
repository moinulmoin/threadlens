# Threadlens V0 Plan

## Goal

Build a reliable local search system for coding-agent sessions across Codex,
Claude Code, Cursor, Pi, OMP, Droid, OpenCode, and future local agents.

Threadlens is not primarily a resume tool. It is a search system. Indexing is
internal plumbing, and resume/open commands are optional result actions.

V0 is done when a user can search rough keywords such as `otp plunk`,
`monorepo split`, `rider modal`, or typo variants, and Threadlens returns the
right local agent sessions grouped by source/session with useful snippets.

## V0 Product Contract

- Local-only session cache backed by SQLite FTS.
- Raw agent session stores remain the source of truth.
- Default sources:
  - Codex JSONL sessions under `~/.codex/sessions`.
  - Claude Code JSONL sessions under `~/.claude/projects` and `~/.claude/history.jsonl`.
  - Cursor local SQLite/session state.
  - Pi JSONL sessions under `~/.pi/agent/sessions`.
  - OMP JSONL sessions under `~/.omp/agent/sessions`.
  - Droid JSONL sessions under `~/.factory/sessions`.
  - OpenCode SQLite sessions under `~/.local/share/opencode/opencode.db` when sessions exist.
- Experimental sources:
  - Custom JSONL source profiles.
- Search returns sessions, not individual message spam.
- Raycast is a thin UI over CLI JSON and must not implement parsing, caching, or ranking.

## Commands

- `threadlens sources`: show discovered local stores.
- `threadlens refresh`: refresh the local searchable cache.
- `threadlens refresh --days 14`: refresh recent work only.
- `threadlens refresh --source <name>`: refresh one built-in or custom source.
- `threadlens refresh --all`: refresh default sources plus custom profiles.
- `threadlens search "query"`: search sessions.
- `threadlens search "query" --json`: JSONL for Raycast and tools.
- `threadlens doctor`: check source readability and adapter health.
- `threadlens brief <result_id>`: print compact session summary.
- `threadlens resume <result_id>`: print verified resume command when available.
- `threadlens eval <eval-file.json>`: run query-to-session retrieval tests.
- `threadlens eval <eval-file.json> --timings`: include per-query timings.
- `threadlens bench <eval-file.json>`: enforce query latency gates.
- `threadlens sources add <name> --path <glob> ...`: register a custom source profile.

`threadlens index` may exist as a compatibility alias, but `refresh` is the
product-facing command.

## Search Contract

Each JSON search result must include:

- `result_id`, formatted as `source:session_id`.
- `source` and `session_id`.
- `cwd`, `title`, and `last_timestamp`.
- `score` and `matched_terms`.
- `best_snippets`, limited to the best few matching messages.
- `source_path` and `source_line`.
- `actions.open_source`.
- `actions.resume_command` only for sources with verified resume syntax.

Ranking should use:

- Exact/BM25 matching.
- Prefix matching fallback.
- Bounded fuzzy matching for typo tolerance.
- Recency boost.
- Project/cwd/title boost.
- Session grouping so one noisy session does not flood the result list.

No semantic embeddings in V0.

## Robustness Contract

- Refresh tracks `source + path + mtime_ns + size` and skips unchanged files.
- If one file/store fails, skip it and continue.
- If an adapter cannot parse a changed format, it must not crash the whole refresh.
- Cursor and OpenCode adapters must fail per store/file when local formats drift.
- The local cache is disposable and rebuildable.
- Custom source profiles are stored in a stable user config path by default and
  must not require code changes for JSONL-compatible agents.

## Evaluation Gate

V0 must pass a real local query-to-session eval:

- At least 10 known target sessions.
- At least 5 positive query variants per session.
- At least 2 negative queries per session.
- Positive queries include exact, partial, typo, project-name, and related wording.
- Acceptance target: Recall@5 >= 90%.
- Negative target: unrelated target session should not appear in top 5.
- Latency target: `threadlens bench` should keep p95 query time below 250ms on
  the current local corpus.

The eval file shape:

```json
[
  {
    "case_id": "vibecms_plunk_otp",
    "target": {
      "source": "claude",
      "session_id": "known-session-id"
    },
    "queries": ["plunk otp", "otp delivery", "email verification"],
    "negative_queries": ["monorepo split", "rider modal"]
  }
]
```

## Raycast V0

Raycast extension behavior:

- Call `threadlens search "<query>" --json`.
- Show source, title/cwd, date, score, and best snippets.
- Actions:
  - Copy result id.
  - Copy source path.
  - Open source file.
  - Copy session brief.
  - Copy resume command when present.

No Raycast-side indexing, parsing, or ranking.

## Non-Goals

- Hosted sync.
- Account system.
- Team sharing.
- Semantic embeddings.
- Background daemon.
- TUI.
- Unverified Cursor resume/open behavior.
