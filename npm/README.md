# threadlens (npm)

Local cross-harness search for coding-agent sessions.

```bash
npm install -g threadlens
threadlens start
threadlens search "plunk otp"
```

Or run it once without installing:

```bash
npx threadlens search "plunk otp"
```

## Requirements

threadlens is a pure-Python CLI (stdlib only). This npm package is a thin
launcher that runs the bundled source with **your** Python, so it needs:

- **Python 3.10+** on your `PATH`

macOS and most Linux distros already ship `python3`. If yours doesn't, install
Python, or use the Python-native distribution which can fetch Python for you:

```bash
uv tool install threadlens     # then run `threadlens`
uvx threadlens search "..."    # run without installing
```

Use a specific interpreter with `THREADLENS_PYTHON=/path/to/python`.

See the [project README](https://github.com/moinulmoin/threadlens#readme) for
full usage.
