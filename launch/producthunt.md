# Product Hunt Draft

## Name

Threadlens

## Tagline

Local search for coding-agent sessions.

## Description

Threadlens helps developers search local coding-agent session history from one
place. V0 supports Codex, Claude Code, Cursor, Pi, OMP, Droid, OpenCode, and
custom JSONL agent sources through config.

It uses a local SQLite FTS cache with prefix and typo-tolerant fallbacks, then
returns session-level results with snippets, cwd, source path, and optional
resume commands.

No hosted sync, no account system, no embeddings in V0. The goal is simple:
find the agent session you half-remember.

## Maker Comment

I built Threadlens because my useful work history was scattered across Codex,
Claude Code, Cursor, and local agent harnesses.

The first version is deliberately narrow. It reads local transcript stores,
builds a disposable SQLite cache, and gives you fast session-level search from
the CLI or Raycast. Raw sessions remain the source of truth, and transcript
content is not uploaded.

I chose keyword/prefix/typo-tolerant search before embeddings because the first
problem is reliability: can I find the session from the rough words I remember?

V0 supports Codex, Claude Code, Cursor, Pi, OMP, Droid, OpenCode, and custom
JSONL agents through source profiles.

## Gallery Ideas

- Terminal search result with grouped sessions.
- Raycast search result list.
- Custom source profile command.
- `doctor` output showing readable sources.
- Evaluation result showing Recall@5 and p95 latency.

## Categories

- Developer Tools
- Productivity
- Artificial Intelligence

## First Comment CTA

Try the CLI first, then wire the Raycast extension if you want a faster local UI.
