# Threadlens Positioning

## Product

Threadlens is a local-first search system for coding-agent sessions.

It helps developers answer:

- Where did I debug this?
- Which agent session had that plan?
- What project did I run that command in?
- Which Claude/Codex/Cursor thread mentioned this error?

## Audience

Primary audience:

- Developers who use more than one coding agent.
- People switching between Codex, Claude Code, Cursor, and local harnesses.
- Builders with lots of parallel experiments, worktrees, and terminal sessions.

Secondary audience:

- Teams that want local personal search before thinking about sync.
- Agent-tool builders who need a simple adapter model for their own sessions.

## Core Problem

Coding agents create useful work history, but each tool stores it differently.
Built-in search is usually scoped to one app, tied to one UI, or too weak for
messy real-world recall.

The user does not want a memory product first. They want to type a rough query
and find the session.

## Promise

Search local coding-agent sessions from one place.

Threadlens turns local session stores into a fast searchable cache, grouped
by source and session, with snippets and optional actions like copy resume
command.

## V0 Message

Threadlens V0 is:

- Local-first.
- CLI-first.
- Raycast-ready.
- Built on SQLite FTS.
- Designed for Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, and OpenCode local
  stores.
- Extensible with custom JSONL source profiles.
- Conservative about local formats that can drift, especially Cursor and
  OpenCode.

## Strong Claims We Can Make

- Local sessions stay local.
- Threadlens does not upload session content.
- The cache is disposable and rebuildable from the raw agent session stores.
- Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, and OpenCode are built-in sources.
- OpenCode is indexed when its local database contains sessions.
- Custom JSONL agents can be added without code changes.
- Raycast is a thin UI over the CLI.
- Search returns sessions with useful snippets, not message spam.
- V0 intentionally does not require embeddings or a hosted service.

## Claims To Avoid

- "Searches every agent" unless qualified with supported sources.
- "Semantic search" for V0. Say keyword, prefix, and typo-tolerant search.
- "Private by design" without explaining local-only behavior.
- "Perfect recall" or "never lose a thread again."
- "Resume any session" because resume commands depend on each agent.
- "Cursor/OpenCode formats are stable forever."

## Differentiation

Most agent UIs treat session history as app-local UX. Threadlens treats session
history as local data with adapters.

The important design choices:

- Search is the product. Indexing is plumbing.
- Raw session stores remain the source of truth.
- The cache can be deleted at any time.
- Ranking is explainable: exact, prefix, typo-tolerant fallback, recency, and
  project/title boosts.
- Custom sources are configured with field paths and globs, not plugin code.

## One-Liners

Short:

> Local search for coding-agent sessions.

Practical:

> Search Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, and custom local
> agent sessions from one CLI or Raycast command.

For launch:

> Threadlens finds the coding-agent session you half-remember, without uploading
> your sessions.

For shadcn reply:

> Built the boring version that should actually hold up: local SQLite FTS over
> Codex, Claude, Cursor, Pi, OMP, Amp, Droid, OpenCode, and custom sources, grouped
> session results, snippets, and copyable resume/open actions.
