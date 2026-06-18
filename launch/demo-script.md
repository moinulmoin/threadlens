# Demo Script

## Goal

Show that Threadlens solves one concrete workflow:

> I remember a few words from an old agent session. Threadlens finds the right
> session, shows useful context, and gives me the next action.

Target length: 60-90 seconds.

## Setup

Use a local demo-safe corpus. Do not show private session content unless it
has been reviewed.

Recommended demo sources:

- Public custom-source fixture for a safe baseline.
- A redacted local corpus for realistic latency and result grouping.

## Shot List

1. Problem frame, 5 seconds

   Show a terminal with several agent names in text:

   ```text
   Codex
   Claude Code
   Cursor
   custom local agents
   ```

   Narration:

   > Coding agents remember the work, but the history is split across tools.

2. Health check, 8 seconds

   ```bash
   threadlens doctor
   ```

   Narration:

   > Threadlens checks local session stores first, so you know which sources are
   > readable before searching.

3. Refresh, 8 seconds

   ```bash
   threadlens refresh --days 14
   ```

   Narration:

   > Refresh builds a disposable local SQLite cache and skips unchanged files on
   > later runs.

4. Search, 15 seconds

   ```bash
   threadlens search "otp plunk"
   threadlens search "monorepo splt"
   ```

   Narration:

   > You can search rough keywords, partial wording, and small typos. Results
   > come back grouped by session instead of flooding you with messages.

5. Inspect result, 10 seconds

   ```bash
   threadlens brief codex:<session-id>
   ```

   Narration:

   > A brief gives you the source, project directory, timestamp, and matching
   > snippets.

6. Action, 8 seconds

   ```bash
   threadlens resume codex:<session-id>
   ```

   Narration:

   > When a source has verified resume syntax, Threadlens prints a copyable
   > command. Otherwise it still gives you the source path and context.

7. Raycast, 12 seconds

   Show Raycast search results if available.

   Narration:

   > Raycast is a thin UI over the same CLI. No second index, no separate
   > ranking logic.

8. Close, 5 seconds

   Narration:

   > Threadlens is not hosted memory. It is fast local search for the agent
   > sessions already on your machine.

## Demo Safety Notes

- Do not show raw private session excerpts without review.
- Prefer `--json` only when recording a scripted UI, because JSON can expose
  source paths and snippets.
- Blur usernames, home paths, API names, and customer/project names if needed.
- Keep the message honest: V0 is keyword/prefix/typo-tolerant search, not
  semantic embeddings.

## Optional 30 Second Script

> I built Threadlens because I keep switching between Codex, Claude Code,
> Cursor, and local agent harnesses.
>
> It searches the local session stores from one CLI or Raycast command. Refresh
> builds a disposable SQLite cache, search returns session-level results with
> snippets, and resume prints a command when the source supports it.
>
> No cloud, no sync, no embeddings in V0. Just fast local search for the coding
> agent work you already did.
