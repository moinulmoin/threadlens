# threadlens (npm)

Local cross-harness search for coding-agent sessions.

```bash
npm install -g threadlens
threadlens search "plunk otp"
threadlens skill
```

Or run once without installing:

```bash
npx threadlens search "plunk otp"
```

## How it works

This package ships a tiny JS shim (`bin/threadlens.js`) with no vendored Python.
Installing it pulls in the matching pre-built native binary via npm's
`optionalDependencies` mechanism — exactly the way esbuild distributes its binary.

| Platform | Package pulled |
|---|---|
| macOS arm64 | `@moinulmoin/threadlens-darwin-arm64` |
| macOS x64   | `@moinulmoin/threadlens-darwin-x64`   |
| Linux x64 (glibc) | `@moinulmoin/threadlens-linux-x64-gnu` |

The binary is a self-contained [PyInstaller](https://pyinstaller.org/) onedir
bundle — no Python required on the host machine.

## Requirements

- **Node.js 16+** (for the shim)
- One of the supported platforms above
- No Python required

## Override / escape hatches

**Point at a custom binary:**
```bash
THREADLENS_BINARY=/path/to/threadlens threadlens search "..."
```

**Installed with `--omit=optional`?** The shim will print a clear error. Fix it:
```bash
npm install -g threadlens   # re-install without --omit=optional
```

**Unsupported platform or prefer Python?**
```bash
uv tool install threadlens       # installs from PyPI, brings its own Python
uvx threadlens search "..."      # run without installing
```

Or download a release archive directly from
<https://github.com/moinulmoin/threadlens/releases>.

## Binary resolution order

1. `THREADLENS_BINARY` environment variable (if set, used verbatim)
2. Platform lookup: `${process.platform}-${process.arch}` → scoped package name
3. `require.resolve('<pkg>/package.json')` to locate the package directory
4. Execute `<pkgDir>/bin/threadlens/threadlens` with all args forwarded

If step 2 or 3 fails, the shim exits 127 with a diagnostic message.

## Development

```bash
# Regenerate platform package scaffolds and sync version from threadlens/__init__.py
node scripts/sync.mjs

# Run the shim unit tests (no binaries needed)
node --test npm/test/shim.test.mjs
```

See the [project README](https://github.com/moinulmoin/threadlens#readme) for
full usage and source.
