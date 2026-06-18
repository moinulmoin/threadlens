# Threadlens Launch Kit

This folder contains the launch material for Threadlens V0.

Threadlens is a local-first search tool for coding-agent sessions. The public
message should stay tight: it searches local Codex, Claude Code, Cursor, Pi,
OMP, Amp, Droid, and OpenCode sessions where local stores exist, supports custom
JSONL agent sources, and exposes both CLI and Raycast workflows.

## Assets

- [Positioning](positioning.md): audience, problem, promise, claims, non-claims.
- [Announcement Copy](announcement.md): X posts, shadcn reply, launch thread,
  GitHub release notes, and community posts.
- [Demo Script](demo-script.md): 60-90 second launch demo plan and shot list.
- [FAQ](faq.md): answers for privacy, indexing, semantic search, custom agents,
  Cursor, resume commands, and reliability.
- [Launch Checklist](launch-checklist.md): final gates before publishing.
- [Product Hunt Draft](producthunt.md): optional listing copy.

## Launch Principle

Do not sell Threadlens as "AI memory" or "universal agent recall." Sell the
thing that works:

> Fast local search across coding-agent session transcripts, with reliable
> grouping, snippets, and copyable actions.

V0 is intentionally boring under the hood: SQLite FTS, prefix matching, bounded
fuzzy fallback, file-level refresh tracking, and source adapters. That is the
point.
