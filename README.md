# Threadlens

![Threadlens logo](assets/threadlens-logo.svg)

[![PyPI version](https://img.shields.io/pypi/v/threadlens?logo=pypi&logoColor=white&color=3775a9)](https://pypi.org/project/threadlens/)
[![Python](https://img.shields.io/pypi/pyversions/threadlens?logo=python&logoColor=white)](https://pypi.org/project/threadlens/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/moinulmoin/threadlens)

**Find the coding-agent session you half-remember. Keep the history on your machine.**

Threadlens searches local sessions from Codex, Claude Code, Cursor, Pi, OMP,
Amp, Droid, OpenCode, and custom JSONL agents through one CLI. It turns rough
memories such as `plunk otp`, `monorepo split`, or a typo into grouped session
results with useful snippets and optional resume actions.

```bash
uv tool install threadlens
threadlens start
threadlens search "plunk otp"
```

Threadlens does not upload sessions. It reads the original local stores into a
private, disposable SQLite FTS index that you can refresh or rebuild at any time.

## Why Threadlens

- **Search across agents.** One query covers supported local session stores.
- **Search the way you remember.** Exact, prefix, partial, and bounded
  typo-tolerant matching help when the wording is fuzzy.
- **Return sessions, not message spam.** Matches are grouped with titles,
  working directories, timestamps, and the best snippets.
- **Stay local.** No hosted sync, account, embeddings API, or background daemon.
- **Use it anywhere.** Search from the terminal, Raycast, scripts, or a bundled
  agent `SKILL.md`.

## Supported sources

| Source | Local store | Notes |
| --- | --- | --- |
| Codex | JSONL sessions | Search and verified resume command |
| Claude Code | JSONL sessions and history | Search and verified resume command |
| Cursor | Local SQLite state | Best-effort because the private format can change |
| Pi | JSONL sessions | Search and verified resume command |
| OMP | JSONL sessions | Search and verified resume command |
| Amp | Local prompt history | Prompts only; the observed store has no assistant history or resumable IDs |
| Droid | JSONL sessions | Search and verified resume command |
| OpenCode | Local SQLite database | Available when the database contains sessions |
| Custom agents | Configured JSONL files | Add a profile without changing Threadlens code |

Raw stores remain the source of truth. Threadlens never writes to them.

## Install

Threadlens is a Python CLI distributed through PyPI. It does not ship native
executables or platform-specific binary downloads.

> [!NOTE]
> The old npm and standalone builds stop at 1.2.2 and will not receive updates.
> Install Threadlens 1.3.0 or newer with `uv` or `pipx`. If
> `command -v threadlens` still points to an npm shim, remove that old global
> package to avoid a `PATH` conflict.

### uv (recommended)

[`uv`](https://docs.astral.sh/uv/) can install Threadlens and manage a compatible
Python automatically:

```bash
uv tool install threadlens
```

Run it once without installing:

```bash
uvx threadlens search "plunk otp"
```

### pipx or pip

```bash
pipx install threadlens
# or
pip install threadlens
```

Threadlens requires Python 3.10 or newer.

### From source

```bash
git clone https://github.com/moinulmoin/threadlens.git
cd threadlens
uv tool install .
make verify
```

After changing the checkout, reinstall with `uv tool install --reinstall .`.

## Core workflow

### 1. Build the local index

```bash
threadlens start
```

`start` discovers supported stores, creates the local index, and prints useful
next commands. Running `search` against an empty index performs the same initial
setup unless `--no-bootstrap` is passed.

### 2. Search what you remember

```bash
threadlens search "plunk otp"
threadlens search "monorepo api split" --source codex
threadlens search "rider modal" --cwd /path/to/project --limit 20
```

Use JSON Lines for integrations:

```bash
threadlens search "plunk otp" --json --no-bootstrap
```

Each JSON result includes a stable result ID, source, session ID, title, working
directory, timestamp, score, matched terms, snippets, source location, freshness
metadata, and supported actions.

### 3. Refresh when sessions change

```bash
threadlens refresh
threadlens refresh --days 14
threadlens search "plunk otp" --fresh
```

Refresh tracks file modification time and size, so unchanged files are skipped.
Use `--force` to reprocess matching files or `--reset` for a clean rebuild:

```bash
threadlens refresh --force
threadlens refresh --reset
```

### 4. Inspect and continue a result

```bash
threadlens brief codex:019...
threadlens resume codex:019...
```

`resume` prints a command; it never executes it. Resume actions are emitted only
for agents whose local command syntax has been verified.

## Useful commands

```bash
threadlens sources                         # show detected stores
threadlens doctor                          # check adapters and index readiness
threadlens stats                           # show indexed message/session counts
threadlens search "query" --source claude  # filter by source
threadlens search "query" --cwd "$PWD"     # filter by project tree
```

Global options must appear before the subcommand:

```bash
threadlens --db /tmp/threadlens/index.sqlite refresh
threadlens --db /tmp/threadlens/index.sqlite search "cursor composer"
threadlens --config /tmp/threadlens/sources.json sources
```

By default, the index lives in the platform's user data directory and custom
source profiles live in its user configuration directory.

## Raycast

The [`raycast/`](raycast/) directory contains a thin Raycast extension over
`threadlens search --json`. It renders results and actions but does not index,
parse, or rank sessions itself.

Install the CLI first:

```bash
uv tool install threadlens
```

The extension finds common CLI locations such as `~/.local/bin`,
`/opt/homebrew/bin`, and `/usr/local/bin`. If needed, set **Threadlens Command**
to the full output of `command -v threadlens`.

For local extension development:

```bash
cd raycast
npm install
npm run dev
```

Then run **Search Agent Sessions** in Raycast. You can also use Raycast's
**Import Extension** command and select the repository's `raycast/` directory.

## Bundled agent skill

The Python package includes a `SKILL.md` that teaches compatible coding agents
when and how to retrieve prior local sessions with Threadlens.

Print its durable installed path:

```bash
threadlens skill
threadlens skill --json
```

Copy or symlink the reported `threadlens` directory into the host agent's skills
directory. The skill uses the installed CLI; it does not download or execute a
standalone binary. The Raycast extension remains independent of the skill.

## Custom JSONL agents

Add a named source profile when another agent stores sessions as JSONL:

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

threadlens refresh --source aider
threadlens search "custom agent bug" --source aider
```

Built-in names are reserved. Custom names become result prefixes such as
`aider:session-id`. Resume templates support `{cwd}`, `{session_id}`, and
`{source}`; Threadlens shell-quotes the substituted values.

For an unnamed one-off JSONL root:

```bash
threadlens refresh --include ~/.local/share/my-agent/sessions
```

## Privacy and safety

- Session data and the search index stay on the local machine.
- Source stores are read-only inputs; the SQLite index is disposable.
- User and assistant messages are indexed where the source format identifies
  roles. System/developer instructions, thinking blocks, and tool output are
  skipped by supported adapters where those fields are distinguishable.
- Generic and Cursor extraction skip obvious credential fields.
- Display-time redaction masks common token and credential shapes.
- Session content is treated as untrusted data. Threadlens does not execute it
  or follow instructions found inside it.
- Index and profile files use private filesystem permissions where supported.
  Threadlens creates its own storage directories privately and never changes the
  permissions of a parent directory that already exists.

See [SECURITY.md](SECURITY.md) for the full data boundary and reporting guidance.

## Platform support

Threadlens runs wherever Python 3.10+ runs. Source discovery depends on where
each agent stores its local data:

- **macOS:** fully supported and tested.
- **Linux:** supported, including XDG locations for Cursor, Amp, and OpenCode.
- **Windows:** implemented as best-effort but not yet validated on a physical
  Windows machine. Cursor, Amp, and OpenCode discovery checks `%APPDATA%` and
  `%LOCALAPPDATA%`. Please report confirmed paths in
  [issue #1](https://github.com/moinulmoin/threadlens/issues/1).

## Updating

Use the same tool you installed with:

```bash
uv tool upgrade threadlens
pipx upgrade threadlens
pip install --upgrade threadlens
```

The index survives normal upgrades. Run `threadlens refresh --reset` only when
you want to rebuild it from scratch.

## Evaluation and benchmarks

Threadlens includes deterministic retrieval evaluation and latency gates:

```bash
threadlens --db .threadlens/index.sqlite \
  eval .threadlens/eval-local-10.json --timings

threadlens --db .threadlens/index.sqlite \
  bench .threadlens/eval-local-10.json --max-p95-ms 250
```

Private eval files should map remembered queries to known local sessions. The
project acceptance target is Recall@5 >= 90%, no unrelated target sessions in
the top five, and p95 search latency below 250 ms on the current local corpus.

Public custom-source fixtures live under [`eval/`](eval/). Run the complete
project verification suite with:

```bash
make verify
```

## Project boundaries

Search is the product. Indexing is local plumbing, and resume/open commands are
optional result actions. Threadlens intentionally has no hosted sync, account
system, team sharing, semantic embeddings, or background daemon.

## Documentation

- [Architecture](ARCHITECTURE.md) — adapters, index, ranking, and UI boundary
- [Contributing](CONTRIBUTING.md) — development workflow and adapter rules
- [Security](SECURITY.md) — privacy model and untrusted-session handling
- [Evaluation](eval/README.md) — eval formats and acceptance testing

Built by [moinulmoin](https://moinulmoin.com) ·
[@moinulmoin](https://x.com/moinulmoin) · MIT licensed
