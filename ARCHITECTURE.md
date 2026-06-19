# Architecture

Threadlens is intentionally small: the CLI is the product, SQLite is the local
cache, and Raycast is a thin view over CLI JSON.

## Data Flow

1. Source adapters discover local session stores.
2. `threadlens refresh` extracts user/assistant messages into a private SQLite
   database.
3. Search runs against SQLite FTS5, groups matching messages by session, and
   returns a small result object.
4. Optional actions, such as copyable resume commands, are added at the edge.

Raw agent stores remain the source of truth. The Threadlens database is
disposable and can be rebuilt.

## Package Layout

- `threadlens/`: Python stdlib CLI, source adapters, SQLite store, ranking.
- `tests/`: focused unit tests for extraction, ranking, CLI behavior, profiles.
- `eval/`: public smoke fixtures and private-eval documentation.
- `raycast/`: Raycast extension that calls `threadlens search --json`.

## Source Adapters

Built-in adapters cover Codex, Claude Code, Cursor, Pi, OMP, Amp Code, Droid,
and OpenCode. Amp Code currently indexes the local prompt history file, not a
full assistant session. JSONL-compatible agents can be added with
`threadlens sources add` without changing code.

Adapters must treat session content as untrusted data. They should extract
text and metadata, not execute or follow instructions from sessions.

## Ranking

V0 uses deterministic local ranking:

- SQLite FTS exact matching.
- Prefix fallback.
- Bounded fuzzy fallback for typos.
- Recency and cwd/title boosts.
- Session grouping to avoid message spam.

There are no embeddings, hosted sync, background daemon, or cloud calls in V0.

## CLI And UI Boundary

The CLI owns indexing, parsing, ranking, and result actions. Raycast only calls
the CLI and renders returned JSONL. Any future UI should keep the same boundary
unless there is a concrete reason to move product logic out of the CLI.
