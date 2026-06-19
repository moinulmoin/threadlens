# Threadlens Changelog

## [Bundled CLI — no separate install] - 1.1.0

- The extension now ships a per-architecture macOS binary (arm64 / x64) inside `assets/bin/`. No separate CLI install is required.
- The "Threadlens Command" preference is now optional. Leave it blank to use the bundled binary; set it to a full path only as an advanced override.

## [Initial Release] - {PR_MERGE_DATE}

- Search local coding-agent sessions from Raycast — Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode, and custom JSONL sources.
- Thin UI over the Threadlens CLI's JSON interface (no separate indexing or ranking).
- Grouped session results with snippets, source, timestamp, working directory, and copyable resume/open actions.
