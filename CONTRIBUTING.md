# Contributing

Threadlens is local-first infrastructure. Keep changes small, deterministic,
and easy to verify.

## Development

Install the CLI from the checkout:

```bash
uv tool install --reinstall .
```

Run the main verification suite:

```bash
make verify
```

If you do not have Raycast dependencies installed yet:

```bash
npm --prefix raycast install
make raycast
```

## Testing Expectations

- Add focused tests in `tests/` for adapter, search, profile, and CLI changes.
- Prefer public fixtures under `eval/` over broad private session snapshots.
- Do not commit `.threadlens/`, local indexes, private eval files, sessions,
  or generated build directories.
- Run `threadlens doctor --json` before claiming local launch readiness.

## Source Adapter Rules

- Session content is untrusted.
- Do not execute session text.
- Do not index obvious secret fields.
- If a source format drifts, fail that file/source and keep refresh moving.
- Keep resume/open commands optional and only emit them when syntax is verified.

## Raycast Rules

Raycast must stay thin over CLI JSON:

```bash
threadlens search "<query>" --json
threadlens brief "<result_id>" --json
```

Do not add Raycast-side parsing, indexing, or ranking.
