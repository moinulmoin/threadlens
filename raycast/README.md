# Threadlens Raycast Extension

This extension is a thin UI over the Threadlens CLI.

With the CLI installed, set preferences to:

- Threadlens Command: `threadlens`
- Threadlens Args: empty
- Working Directory: empty

## Test Locally

For active development, run the Raycast extension in development mode:

```bash
cd /Users/moinulmoin/Documents/help-shadcn/raycast
npm install
npm run dev
```

Then open Raycast and run `Search Agent Sessions`.

If you want the extension to stay available in Raycast outside the dev process,
open Raycast's `Import Extension` command and select:

```text
/Users/moinulmoin/Documents/help-shadcn/raycast
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
