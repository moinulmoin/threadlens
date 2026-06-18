# Threadlens Raycast Extension

This extension is a thin UI over the Threadlens CLI.

With the CLI installed, set preferences to:

- Threadlens Command: `threadlens`
- Threadlens Args: empty
- Working Directory: empty

## Test Locally

For active development, run the Raycast extension in development mode:

```bash
cd raycast
npm install
npm run dev
```

Then open Raycast and run `Search Agent Sessions`.

If you want the extension to stay available in Raycast outside the dev process,
open Raycast's `Import Extension` command and select:

```text
<repo>/raycast
```

After importing, search for `Search Agent Sessions` in Raycast's root search.
If Raycast asks which command to import, choose `threadlens`.

If Raycast shows `Missing executable`, remove the old imported Threadlens
extension in Raycast, quit and reopen Raycast, then run `npm run dev` again from
this directory.

If Raycast shows `spawn threadlens ENOENT`, the extension could not find the CLI
binary in Raycast's GUI environment. The extension automatically adds common
install paths such as `~/.local/bin`, `/opt/homebrew/bin`, and `/usr/local/bin`.
If the error still appears, set the `Threadlens Command` preference to the full
path from:

```bash
command -v threadlens
```

## Checks

```bash
npm exec -- tsc --project tsconfig.json --noEmit
npm run lint
npm run build
```

The extension calls:

```bash
threadlens search "<query>" --json
threadlens brief "<result_id>" --json
```

It does not index, parse, or rank sessions itself.
