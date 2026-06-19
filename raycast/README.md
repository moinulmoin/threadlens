# Threadlens Raycast Extension

This extension bundles the Threadlens CLI binary — no separate install is needed.

## Bundled binary layout

The build system populates `assets/bin/` before the extension is packaged:

```
raycast/assets/bin/
  darwin-arm64/
    threadlens/
      threadlens          ← executable
      _internal/          ← PyInstaller support files
  darwin-x64/
    threadlens/
      threadlens
      _internal/
```

At runtime the extension selects the correct binary from `environment.assetsPath`:

- `arm64` → `assets/bin/darwin-arm64/threadlens/threadlens`
- `x64`   → `assets/bin/darwin-x64/threadlens/threadlens`

## Advanced: custom CLI path

Leave the **Threadlens Command** preference blank to use the bundled binary.
Set it to a full path (e.g. `/usr/local/bin/threadlens`) to override it.

If the bundled binary is missing or not executable the extension shows a clear
error with instructions to reinstall or point to a local install:

```bash
uv tool install threadlens   # recommended
npm install -g threadlens
```

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

The result list is optimized for scanning: title, cwd, agent, date, and score.
Press Enter on a result to open snippets, metadata, and copy/open actions.
