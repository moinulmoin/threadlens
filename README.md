# Threadlens

![Threadlens logo](assets/threadlens-logo.svg)

[![PyPI version](https://img.shields.io/pypi/v/threadlens?logo=pypi&logoColor=white&color=3775a9)](https://pypi.org/project/threadlens/)
[![Python](https://img.shields.io/pypi/pyversions/threadlens?logo=python&logoColor=white)](https://pypi.org/project/threadlens/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/moinulmoin/threadlens)

**Find the coding-agent session you half-remember—without sending your history
anywhere.**

Threadlens searches local sessions from Codex, Claude Code, Cursor, Pi, OMP,
Amp, Droid, OpenCode, and custom JSONL agents through one CLI. Search with the
few words you remember; Threadlens returns the relevant sessions, useful
snippets, and safe ways to continue the work.

```bash
threadlens search "plunk otp"
```

No account. No hosted sync. No Threadlens native binary to sign or trust. Your
source sessions stay untouched on your machine.

## Choose your setup

| I want to…                                              | Start here                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------------ |
| Let my coding agent install, diagnose, and configure it | [Copy the agent setup prompt](#set-up-threadlens-with-your-agent)  |
| Install it myself                                       | [Follow the human quick start](#set-up-threadlens-yourself)        |
| Add Threadlens to Raycast                               | [Set up Raycast](#raycast)                                         |
| Teach my agent to search old sessions whenever needed   | [Install the bundled skill](#give-your-agent-the-threadlens-skill) |

## Why use Threadlens?

Agent history is useful until you cannot remember which tool, project, or
session contains the answer. Threadlens gives those separate local stores one
search interface.

- **Search across agents.** One query covers every supported store detected on
  your machine.
- **Search imperfect memories.** Exact, prefix, partial, and bounded
  typo-tolerant matching handle fragments such as `monorepo split` or
  `raycast executable`.
- **Get sessions, not message spam.** Results are grouped by session with the
  project, timestamp, matched terms, and best snippets.
- **Keep control of the data.** Threadlens reads local stores into a private,
  disposable SQLite index. It never uploads or changes the originals.
- **Use the same search everywhere.** The CLI powers terminal workflows,
  scripts, Raycast, and the bundled agent skill.

## Set up Threadlens with your agent

Paste the prompt below into Codex, Claude Code, Cursor, or another coding agent
that can use a terminal. It gives the agent enough authority to complete normal
setup while keeping destructive and privacy-sensitive decisions with you.

```text
Set up Threadlens, a local-first search CLI for my coding-agent sessions.

Goal:
- Install or upgrade the official Python CLI from PyPI.
- Make its bundled Threadlens skill available to this agent when the host has a
  supported local skills directory.
- Detect my local agent stores, build the index, and verify that search is ready.

You may:
- Inspect my OS, PATH, Python, uv, pipx, and existing Threadlens installation.
- Install or upgrade Threadlens in my user environment with uv or pipx.
- Run Threadlens sources, doctor, start, refresh, stats, skill, and a harmless
  verification search.
- Request read-only access to the specific local session paths Threadlens needs
  if your sandbox blocks them.
- Copy or symlink the bundled Threadlens skill into this agent host's local
  skills directory if you can identify that directory safely. Do not overwrite
  an existing skill without asking me.

Do not:
- Download a native executable or install the discontinued npm package.
- Use sudo, chmod, or chown to bypass a permission problem.
- Expose session text, credentials, tokens, or private paths in public output.
- Execute a resume command; `threadlens resume` should only print it.

Ask me before:
- Uninstalling an old package.
- Editing PATH, shell startup files, or agent configuration.
- Changing macOS/Windows privacy settings or other OS-level permissions.
- Adding a custom source profile.

Procedure:
1. Check the platform and run the appropriate PATH lookup: use
   `command -v threadlens` on macOS/Linux or `Get-Command threadlens` in
   PowerShell. Then check `threadlens --version` if present.
2. If an old npm/standalone installation is taking precedence, explain the
   conflict and ask before removing it or changing PATH.
3. Install with `uv tool install threadlens` or upgrade with
   `uv tool upgrade threadlens`. If uv is unavailable, use
   `pipx install threadlens` / `pipx upgrade threadlens`. If neither tool exists,
   explain the smallest safe prerequisite and ask before installing it.
4. Run `threadlens sources` and `threadlens doctor --json`. Inspect the per-source
   errors and index status; do not assume exit code 0 means every source is
   readable.
5. If access is blocked, request only the read access you need. If the operating
   system itself blocks a path, tell me which host application and path need
   access, then wait for me to change the setting.
6. Run `threadlens start`, followed by `threadlens doctor --json` and
   `threadlens stats`.
7. Run `threadlens skill --json`. If this agent host supports local skills,
   install that reported directory using the host's documented convention and
   report exactly what you changed.
8. Verify with a narrow, non-sensitive search such as
   `threadlens search "setup" --limit 3`. Summarize results without printing long
   session excerpts.

Finish by reporting:
- Installed version and resolved command path.
- Sources detected, sources indexed, and any partial coverage.
- Index readiness and the command I should use for my first real search.
- Whether the skill was installed, and its destination.
- Anything that still requires my approval or an OS settings change.
```

The agent should stop and ask when its own sandbox or your operating system
requires approval. That is expected; Threadlens does not need broad filesystem
permissions to work.

## Set up Threadlens yourself

### 1. Install the CLI

[`uv`](https://docs.astral.sh/uv/) is recommended because it installs the CLI in
an isolated environment and can manage a compatible Python version for it:

```bash
uv tool install threadlens
```

Or use `pipx`:

```bash
pipx install threadlens
```

Threadlens requires Python 3.10 or newer. To try one command without keeping an
installation:

```bash
uvx threadlens search "plunk otp"
```

### 2. Discover and index your sessions

```bash
threadlens start
```

`start` discovers readable supported stores, creates the private local index,
and reports whether setup is ready or partial. It is safe to run again when you
want to repair setup.

### 3. Search what you remember

```bash
threadlens search "plunk otp"
threadlens search "monorepo api split" --source codex
threadlens search "rider modal" --cwd /path/to/project --limit 20
```

### 4. Inspect or continue a result

Copy the result ID shown by search:

```bash
threadlens brief codex:019...
threadlens resume codex:019...
```

`brief` shows compact session context. `resume` only prints a verified command;
it never executes that command for you.

## Everyday commands

| Command                             | What it does                                                      |
| ----------------------------------- | ----------------------------------------------------------------- |
| `threadlens search "words"`         | Search indexed sessions; initializes an empty index automatically |
| `threadlens search "words" --fresh` | Refresh relevant stores before searching                          |
| `threadlens refresh`                | Index new or changed session files                                |
| `threadlens sources`                | Show detected stores and custom profiles                          |
| `threadlens doctor`                 | Explain source readability and index readiness                    |
| `threadlens stats`                  | Show indexed message and session counts                           |
| `threadlens brief <result_id>`      | Show a compact brief for one session                              |
| `threadlens resume <result_id>`     | Print a verified resume command when supported                    |
| `threadlens skill`                  | Print the durable path to the bundled agent skill                 |

Refresh only recent files when the corpus is large:

```bash
threadlens refresh --days 14
```

Use `--force` to reprocess matching files or `--reset` to rebuild the disposable
index:

```bash
threadlens refresh --force
threadlens refresh --reset
```

For scripts and integrations, use JSON:

```bash
threadlens search "plunk otp" --json --no-bootstrap
threadlens brief codex:019... --json
threadlens doctor --json
```

Global options belong before the subcommand:

```bash
threadlens --db /tmp/threadlens/index.sqlite search "cursor composer"
threadlens --config /tmp/threadlens/sources.json sources
```

## How it works

1. **Discover:** Threadlens locates supported session stores in their standard
   user directories.
2. **Index:** It extracts user and assistant text into a local SQLite FTS index.
   Unchanged files are skipped during later refreshes.
3. **Search:** It ranks matches and groups them by session, then offers optional
   brief and resume actions.

The raw stores remain the source of truth. Threadlens does not write to them,
run a background daemon, or require a network connection at runtime.

## Supported sources

| Source        | Local store                | Coverage                                                                   |
| ------------- | -------------------------- | -------------------------------------------------------------------------- |
| Codex         | JSONL sessions             | Search and verified resume command                                         |
| Claude Code   | JSONL sessions and history | Search and verified resume command                                         |
| Cursor        | Local SQLite state         | Best-effort because the private format can change                          |
| Pi            | JSONL sessions             | Search and verified resume command                                         |
| OMP           | JSONL sessions             | Search and verified resume command                                         |
| Amp           | Local prompt history       | Prompts only; the observed store has no assistant history or resumable IDs |
| Droid         | JSONL sessions             | Search and verified resume command                                         |
| OpenCode      | Local SQLite database      | Available when the database contains sessions                              |
| Custom agents | Configured JSONL files     | Add a profile without changing Threadlens code                             |

Run `threadlens sources` on your machine for the authoritative list of stores it
can currently see.

## Permissions and private data

Threadlens normally needs only:

- read access to the session stores you want to search; and
- write access to its own local index and source-profile directory.

Run this first when a source is missing:

```bash
threadlens doctor
```

The report includes the affected source, path, and read error. Fix permissions
at the narrowest layer that blocked access:

1. **Agent sandbox:** approve read-only access to the reported session directory.
2. **Operating-system privacy control:** grant the host application access to
   the reported location. On macOS, this may be Terminal, your coding-agent app,
   or Raycast. Use Full Disk Access only when a narrower Files and Folders grant
   cannot solve the specific error.
3. **Filesystem ownership:** use the account that owns the sessions. Do not run
   Threadlens with `sudo` and do not make private stores broadly readable with
   `chmod` or `chown`.

Threadlens creates its own data with private permissions where the platform
supports them. It never changes permissions on an existing parent directory.

## Raycast

The [`raycast/`](raycast/) directory contains a thin UI over
`threadlens search --json`. The extension renders results and actions; the CLI
still handles discovery, indexing, and ranking.

Install and initialize the CLI first:

```bash
uv tool install threadlens
threadlens start
```

Install [Threadlens from the Raycast Store](https://www.raycast.com/moinulmoin/threadlens).
To run the repository version locally instead:

```bash
cd raycast
npm install
npm run dev
```

The extension checks common CLI locations including `~/.local/bin`,
`/opt/homebrew/bin`, and `/usr/local/bin`. If it cannot find the command, copy
the full output of `command -v threadlens` into Raycast's **Threadlens Command**
preference.

If Raycast receives an operating-system permission error while the same command
works in Terminal, Raycast itself—not the CLI—needs access to the reported
session location.

## Give your agent the Threadlens skill

The Python package includes a `SKILL.md` that teaches compatible coding agents
when to search, refresh, inspect, and safely cite prior sessions.

Print the installed skill directory:

```bash
threadlens skill
threadlens skill --json
```

Copy or symlink the reported `threadlens` directory into your agent host's local
skills directory, then restart or reload that host if it requires it. The
[agent setup prompt](#set-up-threadlens-with-your-agent) can do this for you when
the host exposes a documented skills directory.

The skill calls the installed CLI. It does not download a binary, execute
session content, or automatically run resume commands.

## Add a custom JSONL agent

Add a named profile when another agent stores sessions as JSONL:

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

Built-in names are reserved. Resume templates support `{cwd}`, `{session_id}`,
and `{source}`; Threadlens shell-quotes substituted values. Omit the resume
template if that agent's resume syntax has not been verified.

For a one-off unnamed JSONL location:

```bash
threadlens refresh --include ~/.local/share/my-agent/sessions
```

## Privacy and safety

- Sessions and the search index stay on the local machine at runtime.
- Original stores are read-only inputs; the SQLite index is disposable.
- Supported adapters skip system/developer instructions, thinking blocks, and
  tool output when the source format distinguishes those fields.
- Generic and Cursor extraction skip obvious credential fields, and display-time
  redaction masks common token and credential shapes.
- Session content is untrusted data. Threadlens never executes it or follows
  instructions found inside it.
- Resume actions are emitted only where the local command syntax has been
  verified, and `resume` prints rather than runs the command.

See [SECURITY.md](SECURITY.md) for the complete data boundary and reporting
guidance.

## Platform support

- **macOS:** supported and tested.
- **Linux:** supported, including XDG locations for Cursor, Amp, and OpenCode.
- **Windows:** implemented as best-effort but not yet validated on a physical
  Windows machine. Cursor, Amp, and OpenCode discovery checks `%APPDATA%` and
  `%LOCALAPPDATA%`. Please report confirmed paths in
  [issue #1](https://github.com/moinulmoin/threadlens/issues/1).

Threadlens is a Python CLI distributed through PyPI. It does not ship native or
platform-specific executables.

## Update or migrate

Use the same tool you installed with:

```bash
uv tool upgrade threadlens
# or
pipx upgrade threadlens
```

The old npm and standalone builds stop at `1.2.2`. To replace a global npm
installation:

```bash
npm uninstall -g threadlens
uv tool install threadlens
command -v threadlens
threadlens --version
```

Normal upgrades keep the index. Use `threadlens refresh --reset` only when you
want a clean rebuild.

## Troubleshooting

### `threadlens: command not found`

Open a new shell after installation. Then check:

```bash
uv tool dir --bin
command -v threadlens
```

With pipx, run `pipx ensurepath` once and open a new shell.

### No sources or no results

```bash
threadlens sources
threadlens doctor
threadlens start
```

No detected store can mean the corresponding agent has no saved sessions in
its standard location. A degraded source means `doctor` found a path but could
not fully read or parse it.

### New sessions are missing

```bash
threadlens search "your query" --fresh
# or
threadlens refresh
```

### The wrong installation runs

Check `command -v threadlens` on macOS/Linux or `Get-Command threadlens` in
PowerShell. Remove an old npm shim or fix PATH so the `uv`/`pipx` installation
comes first.

### Raycast cannot find Threadlens

Set Raycast's **Threadlens Command** preference to the absolute path returned by
`command -v threadlens`. Run `threadlens doctor` in Terminal first to separate a
CLI/index problem from a Raycast PATH or permission problem.

## Develop from source

```bash
git clone https://github.com/moinulmoin/threadlens.git
cd threadlens
uv tool install .
make verify
```

After changing the checkout, reinstall with:

```bash
uv tool install --reinstall .
```

Private retrieval evaluations can be run with:

```bash
threadlens --db .threadlens/index.sqlite \
  eval .threadlens/eval-local-10.json --timings

threadlens --db .threadlens/index.sqlite \
  bench .threadlens/eval-local-10.json --max-p95-ms 250
```

Search is the product. Indexing is local plumbing, and resume/open commands are
optional result actions. Threadlens intentionally has no hosted sync, account
system, team sharing, embeddings API, or background daemon.

## Project documentation

- [Architecture](ARCHITECTURE.md) — adapters, index, ranking, and UI boundary
- [Contributing](CONTRIBUTING.md) — development workflow and adapter rules
- [Security](SECURITY.md) — privacy model and untrusted-session handling
- [Evaluation](eval/README.md) — eval formats and acceptance testing

Built by [moinulmoin](https://moinulmoin.com) ·
[@moinulmoin](https://x.com/moinulmoin) · MIT licensed
