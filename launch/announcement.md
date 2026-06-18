# Announcement Copy

## X Reply To shadcn

Built a first answer: Threadlens.

Local search across coding-agent sessions. Codex, Claude Code, Cursor, Pi, OMP,
Amp, Droid, OpenCode, and custom JSONL sources. SQLite FTS, prefix and
typo-tolerant fallbacks, grouped session results, snippets, Raycast, and
copyable resume/open actions.

No cloud. No embeddings in V0. Just the boring thing that works.

## Short X Post

I built Threadlens: local search for coding-agent sessions.

It indexes local Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, and
custom JSONL sources, then gives you fast session-level results with snippets
from the CLI or Raycast.

No cloud. No hosted sync. Just local search that works.

## Launch Thread

1. I kept forgetting which coding-agent session had the thing I needed.

Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, custom harnesses.
Each has history, but none of it feels like one reliable local search surface.

So I built Threadlens.

2. Threadlens is local search for coding-agent sessions.

V0 searches Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, and custom
JSONL sources.

Results are grouped by source/session, with cwd, timestamps, snippets, and
actions.

3. The implementation is intentionally boring.

SQLite FTS, prefix matching, bounded fuzzy fallback, recency/project/title
boosts, and refresh tracking so unchanged files are skipped.

Raw agent sessions remain the source of truth. The cache is disposable.

4. Custom agents do not need code changes if they write JSONL.

You register a glob, field paths for session/message/text/timestamp/cwd, and an
optional resume template.

Then they show up as first-class searchable sources.

5. There is also a Raycast extension.

It is deliberately thin: it calls the CLI JSON interface and does not implement
its own indexing, parsing, or ranking.

One search brain, multiple surfaces.

6. V0 is not semantic search yet, not hosted memory, and not team sync.

It is the simpler thing I wanted first: search rough keywords or typos and find
the local session fast.

Repo: <repo-url>

## GitHub Release Notes

Threadlens V0 is the first local-first release for searching coding-agent
session transcripts.

Included:

- CLI search over local Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, and OpenCode sessions.
- Custom JSONL source profiles for additional local agents.
- SQLite FTS cache with exact, prefix, and bounded fuzzy matching.
- Session-grouped results with snippets, cwd, timestamps, and source path.
- Optional resume command generation where the agent has verified syntax.
- `doctor`, `brief`, `resume`, `eval`, and `bench` commands.
- Thin Raycast extension over the CLI JSON interface.
- Public custom-source smoke fixture and private-eval workflow.

Not included in V0:

- Hosted sync.
- Account system.
- Team sharing.
- Embeddings or semantic search.
- Background daemon.
- Stable Cursor resume/open behavior.

## Community Post

I built Threadlens, a local-first search tool for coding-agent sessions.

The goal is narrow: find the session, not build a giant memory platform. V0
indexes local Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, and OpenCode
transcripts, and lets you add custom JSONL agent sources with config instead of
code.

Search is backed by SQLite FTS with prefix and typo-tolerant fallbacks. Results
are grouped by session and include useful snippets, cwd, source path, and
optional resume commands.

The Raycast extension is just a UI over the CLI, so ranking and parsing stay in
one place.

Repo: <repo-url>

## README Badge Copy

Local-first search for coding-agent sessions.

## Landing Page H1

Threadlens

## Landing Page Subcopy

Search local Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, and custom
agent sessions from one CLI or Raycast command. Your transcripts stay on your
machine.

## CTA Labels

- Install CLI
- Add Raycast Extension
- Run Doctor
- Add Custom Source
- View Demo
