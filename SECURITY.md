# Security

Threadlens reads local coding-agent sessions. Treat those sessions as
private and untrusted.

## Data Boundary

- V0 is local-only.
- Threadlens does not upload sessions.
- The SQLite index is a local cache and can be deleted or rebuilt.
- Custom source profiles and the default index are stored under user config/data
  directories with private permissions where supported.

## Session Safety

Session text may contain secrets, commands, prompt injections, or misleading
instructions. Threadlens must not execute session content or follow
instructions found inside sessions.

Adapters should avoid indexing obvious credential fields. Do not add docs,
fixtures, logs, screenshots, or launch copy that expose private session
contents or secret values.

## Reporting

For now, report issues directly in the repository issue tracker. Include:

- Threadlens version or commit.
- Operating system.
- Source adapter involved.
- Redacted error output.
- Whether the issue occurs during `refresh`, `search`, `doctor`, Raycast, or
  resume-command generation.
