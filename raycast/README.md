# Threadlens Raycast Extension

This extension is a thin UI over the Threadlens CLI.

With the CLI installed, set preferences to:

- Threadlens Command: `threadlens`
- Threadlens Args: empty
- Working Directory: empty

The extension calls:

```bash
threadlens search "<query>" --json
threadlens brief "<result_id>" --json
```

It does not index, parse, or rank sessions itself.
