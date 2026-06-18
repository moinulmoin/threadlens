# Threadlens

Threadlens is a local-first search tool for coding-agent sessions. It refreshes
local agent session stores into a private SQLite FTS cache so you can answer
questions like:

> Where did I debug the Plunk OTP issue?

It does not upload transcripts. Raw agent session stores remain the source of
truth; the Threadlens index is disposable and rebuildable.

## Status

V0.1 is focused on reliable local keyword, prefix, and typo-tolerant search.
There are no embeddings, hosted sync, background daemon, or team features.

## Project Docs

- [Architecture](ARCHITECTURE.md): source adapters, SQLite cache, ranking, and
  Raycast boundary.
- [Contributing](CONTRIBUTING.md): local development, tests, and adapter rules.
- [Security](SECURITY.md): local data boundary and transcript safety.
- [Evaluation](eval/README.md): public smoke tests and private acceptance evals.
- [Launch](launch/README.md): launch copy, checklist, and positioning.

## Install

From this checkout:

```bash
uv tool install .
```

Then use the installed CLI:

```bash
threadlens start
threadlens search "plunk otp"
```

If Threadlens is already installed from this checkout, refresh the installed
tool after changes:

```bash
uv tool install --reinstall .
```

Verify the checkout:

```bash
make verify
```

## Initial Scope

- In scope: local-only search, Codex JSONL, Claude Code JSONL, Cursor local SQLite records, Pi JSONL, Oh My Pi/OMP JSONL, Amp Code prompt history, Droid JSONL, OpenCode SQLite, custom JSONL source profiles.
- Experimental: Cursor extraction quality depends on Cursor's local storage shape. Amp Code is supported from local prompt history when `~/.local/share/amp/history.jsonl` exists. OpenCode is supported when its local database contains sessions.
- Out of scope for v0: hosted sync, full app UI, embeddings, background daemon, team sharing.

Cursor's storage format is less stable than the JSONL-backed agents. The adapter
is available in the default setup path, but should be treated as best-effort
until validated against more real Cursor stores.

## Usage

Set up the local cache:

```bash
threadlens start
```

`start` discovers built-in sources, explains the local-only SQLite index, indexes
Codex, Claude, Cursor, Pi, OMP, Amp Code, Droid, and OpenCode when local
sessions or prompt history exist, then prints commands to try next.

Search works as the main entrypoint too. If the index is empty, it runs first-time
indexing before searching:

```bash
threadlens search "plunk otp"
```

Wrappers that need fast, side-effect-free search can disable first-time indexing:

```bash
threadlens search "plunk otp" --json --no-bootstrap
```

Refresh the local cache manually:

```bash
threadlens refresh
```

Fast first pass over recent work only:

```bash
threadlens refresh --days 14
```

After the first run, unchanged files are skipped automatically. Use `--force` to
reindex matching files anyway.

Search it:

```bash
threadlens search "plunk otp"
threadlens search "monorepo api split" --source codex --limit 20
threadlens search "plunk otp" --cwd /path/to/project
threadlens search "plunk otp" --json
```

Inspect available sources:

```bash
threadlens sources
```

Current built-in source names:

- `codex`
- `claude`
- `cursor`
- `pi`
- `omp`
- `amp`
- `droid`
- `opencode`

Reset and rebuild:

```bash
threadlens refresh --reset
```

Use another database path:

```bash
threadlens refresh --db /tmp/threadlens.sqlite
threadlens search "cursor composer" --db /tmp/threadlens.sqlite
```

Add custom JSONL roots:

```bash
threadlens refresh --include ~/.omp/local/research
```

Add a named custom agent source:

```bash
threadlens sources add aider \
  --path "~/.aider/**/*.jsonl" \
  --session-key session.id \
  --message-key message.id \
  --role-key message.role \
  --text-key message.content \
  --timestamp-key createdAt \
  --cwd-key cwd \
  --title-key title \
  --resume-template "cd {cwd} && aider --resume {session_id}"
```

Then refresh and search it:

```bash
threadlens refresh --source aider
threadlens search "custom agent bug" --source aider
```

Source profiles are stored in the user config directory by default. Built-in
source names are reserved, and custom source names become first-class result
prefixes such as `aider:session-id`.

Inspect source health:

```bash
threadlens doctor
```

`doctor` reports source readability separately from index readiness. If local
sessions are found but the SQLite index has no searchable messages, it reports
`not_ready` and points to `threadlens start`.

Print a compact session brief:

```bash
threadlens brief codex:019...
```

Print a verified resume command when the source supports one:

```bash
threadlens resume codex:019...
```

Run query-to-session evaluation:

```bash
threadlens eval .threadlens/eval-local-10.json
threadlens eval .threadlens/eval-local-10.json --timings
threadlens bench .threadlens/eval-local-10.json --max-p95-ms 250
```

For a real acceptance gate, create a private eval file with known local session
ids and remembered queries. The target is Recall@5 >= 90% with no unrelated
target sessions in the top 5.

If you are using the repo-local development index, include `--db`:

```bash
threadlens --db .threadlens/index.sqlite eval .threadlens/eval-local-10.json --timings
threadlens --db .threadlens/index.sqlite bench .threadlens/eval-local-10.json --max-p95-ms 250
```

The committed custom-source fixture can be used for a public development smoke
eval without private transcripts:

```bash
mkdir -p /private/tmp/threadlens-smoke
threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json sources add demoagent \
  --path eval/custom-source.example.jsonl \
  --session-key session.id \
  --message-key message.id \
  --role-key message.role \
  --text-key message.content \
  --timestamp-key createdAt \
  --cwd-key cwd \
  --title-key title
threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json refresh --source demoagent --force
threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json eval eval/custom-source.eval.json
```

## Notes

- The cache defaults to a user data directory. Pass `--db` for repo-local or temporary databases.
- Custom source profiles default to a user config directory. Pass `--config` for repo-local or temporary profiles.
- Refresh tracks file `mtime` and size, so repeat runs skip unchanged session files.
- Only user and assistant messages are indexed for Codex and Claude by default.
- Tool output and system/developer instructions are skipped for Codex and Claude.
- Pi, OMP, Droid, and OpenCode adapters index user/assistant text parts and skip thinking/tool blocks.
- Amp Code indexes local prompt history from `~/.local/share/amp/history.jsonl`; the observed local store does not include assistant transcripts, timestamps, or resumable session ids.
- Obvious credential fields are skipped in generic and Cursor extraction.
- Search results are grouped by session and include source, timestamp, cwd, source path, line, snippets, and score.
- Use `--cwd` to restrict search to sessions whose recorded cwd is that directory or a child directory.
- For harnesses with verified local resume syntax, results include a copyable resume command.
- Custom source resume templates support `{cwd}`, `{session_id}`, and `{source}` with shell-quoted values.

Current resume hints:

- Codex: `cd <cwd> && codex resume <session_id>`
- Claude Code: `cd <cwd> && claude --resume <session_id>`
- Pi: `cd <cwd> && pi --session <session_id>`
- OMP: `cd <cwd> && omp --resume <session_id>`
- Droid: `cd <cwd> && droid --resume <session_id>`
- OpenCode: `cd <cwd> && opencode --session <session_id>`
- Amp Code: not emitted yet; the observed local history file does not expose resumable session ids
- Cursor: not emitted yet; the local CLI did not expose a session resume command

## Raycast

The `raycast/` folder contains a thin Raycast extension. It calls the CLI JSON
interface and does not implement its own parsing, indexing, or ranking.

With the CLI installed, configure extension preferences as:

- Threadlens Command: `threadlens`
- Threadlens Args: empty
- Working Directory: empty

Run in development mode:

```bash
cd raycast
npm install
npm run dev
```

Then open Raycast and run `Search Agent Sessions`.

To install it from source instead of only running the dev process, use Raycast's
`Import Extension` command and select:

```text
<repo>/raycast
```

If Raycast asks which command to import, choose `threadlens`.

From the repo root, the same TypeScript check is:

```bash
npm --prefix raycast exec -- tsc --project raycast/tsconfig.json --noEmit
NPM_CONFIG_CACHE=/private/tmp/threadlens-npm-cache npm --prefix raycast run lint
```

If Raycast shows `Missing executable`, remove the old imported extension from
Raycast, quit and reopen Raycast, then run `npm run dev` again from `raycast/`.
That error usually means Raycast is loading a stale imported command bundle.

If Raycast shows `spawn threadlens ENOENT`, set the `Threadlens Command`
preference to the full path from `command -v threadlens`. The extension already
adds common CLI install paths such as `~/.local/bin`, `/opt/homebrew/bin`, and
`/usr/local/bin` before spawning the CLI.
