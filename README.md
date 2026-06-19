# Threadlens

![Threadlens logo](assets/threadlens-logo.svg)

[![npm version](https://img.shields.io/npm/v/threadlens?logo=npm&color=cb3837)](https://www.npmjs.com/package/threadlens)
[![PyPI version](https://img.shields.io/pypi/v/threadlens?logo=pypi&logoColor=white&color=3775a9)](https://pypi.org/project/threadlens/)
[![Python](https://img.shields.io/pypi/pyversions/threadlens?logo=python&logoColor=white)](https://pypi.org/project/threadlens/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Built by [moinulmoin](https://moinulmoin.com) · [@moinulmoin](https://x.com/moinulmoin)

**Find the coding-agent session you half-remember — without uploading your session history.**

Threadlens is a local-first search tool for coding-agent sessions. It refreshes
local agent session stores into a private SQLite FTS cache so you can answer
questions like:

> Where did I debug the Plunk OTP issue?

Your sessions never leave your machine. Raw agent session stores remain the
source of truth; the Threadlens index is disposable and rebuildable.

## Quickstart

```bash
uv tool install threadlens     # recommended (or: npm install -g threadlens)
threadlens start               # discover local sources and build the index
threadlens search "plunk otp"  # search every local agent session at once
```

Searches your local **Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, and
OpenCode** sessions — plus any custom JSONL agent you add with config, not code.

## Status

v1.0 is focused on reliable local keyword, prefix, and typo-tolerant search.
There are no embeddings, hosted sync, background daemon, or team features.

## Platform support

Threadlens runs anywhere Python 3.10+ runs — macOS, Linux, and Windows. What
differs is *source discovery* (where it looks for each agent's local sessions):

- **macOS** — fully supported and tested.
- **Linux** — supported, including Cursor (`$XDG_CONFIG_HOME` / `~/.config/Cursor`)
  and Amp/OpenCode (`$XDG_DATA_HOME` / `~/.local/share`).
- **Windows** — best-effort and **not yet tested on a real Windows machine**.
  Cursor, Amp, and OpenCode are looked up under `%APPDATA%` / `%LOCALAPPDATA%`, but
  the exact store locations are unverified. If a source isn't found, please report
  the real path in [#1](https://github.com/moinulmoin/threadlens/issues/1).

## Project Docs

- [Architecture](ARCHITECTURE.md): source adapters, SQLite cache, ranking, and
  Raycast boundary.
- [Contributing](CONTRIBUTING.md): local development, tests, and adapter rules.
- [Security](SECURITY.md): local data boundary and session safety.
- [Evaluation](eval/README.md): public smoke tests and private acceptance evals.

## Install

PyPI is the lean primary install; npm and the standalone binaries let you install
without managing Python yourself.

### uv / pipx (recommended)

`uv` can fetch a compatible Python for you, so this is the most reliable path:

```bash
uv tool install threadlens     # global install, on your PATH
uvx threadlens search "..."    # run once, without installing
```

`pipx install threadlens` works the same way.

### npm (no Python required)

The npm package selects a prebuilt native binary for your platform via npm's
`optionalDependencies` — the same way esbuild ships its binary — so it needs **no
Python**:

```bash
npm install -g threadlens
npx threadlens search "..."
```

Prebuilt targets: macOS (Apple Silicon + Intel) and Linux x64 (glibc). On other
platforms the shim points you back to the `uv` / `uvx` install above.

### Standalone binary

Every release attaches per-platform archives plus `SHA256SUMS` to the
[GitHub releases](https://github.com/moinulmoin/threadlens/releases). For example,
on Apple Silicon:

```bash
curl -fsSL -o threadlens.tar.gz \
  https://github.com/moinulmoin/threadlens/releases/latest/download/threadlens-darwin-arm64.tar.gz
tar -xzf threadlens.tar.gz            # -> ./threadlens/ (keep the folder together)
./threadlens/threadlens --version
# optional: symlink onto PATH (keep the extracted folder in place)
sudo ln -sf "$PWD/threadlens/threadlens" /usr/local/bin/threadlens
```

Archives are `threadlens-darwin-arm64`, `threadlens-darwin-x64`, and
`threadlens-linux-x64-gnu`. Verify with `shasum -a 256 -c SHA256SUMS`.

### Raycast

Install the **Threadlens** extension from the Raycast store. It bundles the CLI,
so there's nothing else to install — search your local sessions from Raycast.

### From source

```bash
uv tool install .                 # or: uv tool install --reinstall .  after changes
make verify                       # run the project checks
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

## Bundled Codex Skill

Threadlens ships a small Codex skill with the Python package. It teaches an
agent when and how to use the CLI for local session retrieval without turning
Threadlens into a memory product.

After installing the CLI, print the bundled skill path:

```bash
threadlens skill
threadlens skill --json
```

Copy or symlink that `threadlens` skill folder into the agent's local skills
directory when the host supports filesystem skills. The Raycast extension does
not package the skill; it stays a thin UI over the CLI.

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
eval without private sessions:

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
- Amp Code indexes local prompt history from `~/.local/share/amp/history.jsonl`; the observed local store does not include assistant sessions, timestamps, or resumable session ids.
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
