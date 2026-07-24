# Threadlens

Search your local coding-agent sessions from Raycast — across **Codex, Claude Code, Cursor, Pi, OMP, Amp, Droid, OpenCode**, and custom JSONL sources. Nothing leaves your machine.

This extension is a thin UI over the [Threadlens](https://github.com/moinulmoin/threadlens) CLI; it does not index, parse, or rank sessions itself.

## Requirements

Install the Threadlens CLI:

```bash
uv tool install threadlens # recommended; installs a managed Python if needed
# or:
pipx install threadlens

threadlens start
```

The extension looks for `threadlens` on your `PATH` (including `~/.local/bin`, `/opt/homebrew/bin`, and `/usr/local/bin`). If it's installed elsewhere, set the full path in the **Threadlens Command** preference.

If you previously installed the discontinued npm build, confirm that
`command -v threadlens` resolves to the `uv`/`pipx` installation rather than the
old npm shim.

Prefer to let your coding agent handle installation, diagnostics, and the
bundled skill? Copy the
[agent setup prompt](https://github.com/moinulmoin/threadlens#set-up-threadlens-with-your-agent)
from the main README.

## Usage

Open **Search Agent Sessions** and start typing. Results show the session title, agent, working directory, date, and relevance score. Press Enter on a result for snippets, metadata, and copy/open actions.

Under the hood it calls:

```bash
threadlens search "<query>" --json
threadlens brief "<result_id>" --json
```

## Troubleshooting

Run `threadlens doctor` in Terminal first. If the CLI works there but Raycast
reports a permission error, Raycast itself needs access to the session location
named in the error. Grant only that access where possible; Full Disk Access
should be a last resort.

If Raycast cannot find the command, set **Threadlens Command** to the absolute
path returned by `command -v threadlens`.
