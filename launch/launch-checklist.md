# Launch Checklist

## Product Gates

- [ ] `README.md` states the V0 boundary clearly.
- [ ] `PLAN.md` matches actual commands and non-goals.
- [ ] Cursor/OpenCode format-drift caveats are described clearly.
- [ ] Public copy does not claim semantic search.
- [ ] Public copy does not claim universal agent support.
- [ ] Public copy does not expose private transcript snippets.
- [ ] Resume commands are described as optional copyable actions.

## Verification Gates

Run before launch:

```bash
python3 -B -m py_compile threadlens/*.py
python3 -B -m unittest discover -s tests
threadlens doctor --json
```

If using the repo-local private eval database:

```bash
threadlens --db .threadlens/index.sqlite eval .threadlens/eval-local-10.json --timings
threadlens --db .threadlens/index.sqlite bench .threadlens/eval-local-10.json --max-p95-ms 250
```

Run the public smoke fixture:

```bash
threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json sources add demoagent \
  --path eval/custom-source.example.jsonl \
  --session-key session.id \
  --message-key message.id \
  --role-key message.role \
  --text-key message.content \
  --timestamp-key createdAt \
  --cwd-key cwd \
  --title-key title \
  --resume-template "cd {cwd} && demoagent resume {session_id}"

threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json refresh --source demoagent --force
threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json eval eval/custom-source.eval.json
```

Run Raycast checks:

```bash
npm --prefix raycast install
npm --prefix raycast exec -- tsc --project raycast/tsconfig.json --noEmit
NPM_CONFIG_CACHE=/private/tmp/threadlens-npm-cache npm --prefix raycast run lint
NPM_CONFIG_CACHE=/private/tmp/threadlens-npm-cache npm --prefix raycast audit --json
npm --prefix raycast run build
```

## Current Internal Evidence

Last verified in this workspace:

- Python compile: passed.
- Unit tests: 38 passed.
- `doctor --json`: passed.
- Installed CLI index: ready with 109,986 messages.
- Expanded source counts: Codex 26,773, Claude 2,116, Cursor 5, Pi 468, OMP
  53,660, Droid 26,960, OpenCode 4.
- OpenCode source: indexed 4 messages from 1 local session.
- New-source refresh: Pi, OMP, and Droid refreshed into the real user-level
  index.
- Source-restricted searches for Pi, OMP, and Droid returned results with
  copyable resume commands.
- OpenCode source-restricted search returned the new local OpenCode session with
  a copyable `opencode --session` command.
- Installed-index bench: p95 67.3ms, below the 250ms gate.
- `doctor --json` reports the index as ready and reports freshness separately;
  active Codex sessions can still show stale-file hints while the index remains
  usable.
- Legacy private eval fixture: not launch-valid after current Threadlens
  development transcripts included eval labels verbatim; rebuild it with clean
  targets or multi-target equivalents before claiming Recall@5.
- Public custom-source eval: 5/5 positives, 0/2 negatives.
- Raycast TypeScript: passed.
- Raycast lint: passed.
- Raycast audit: 0 vulnerabilities.
- Raycast build: passed.

Do not publish private corpus counts or private query names unless reviewed.

## Release Prep

- [ ] Replace `<repo-url>` placeholders in launch copy.
- [ ] Record demo with reviewed/redacted data.
- [ ] Decide whether to publish Raycast extension now or keep it as local dev
  instructions.
- [ ] Tag the repo after final tests pass.
- [ ] Include install commands in the release post.
- [ ] Open at least one issue for post-V0 semantic search investigation.
- [ ] Open at least one issue for Cursor stabilization.

## Launch Day Order

1. Run final verification gates.
2. Create release tag.
3. Publish GitHub release notes.
4. Publish short X post.
5. Reply to shadcn with the concise version.
6. Publish the longer thread.
7. Share in relevant developer communities.
8. Watch issues for source-format failures and install friction.

## Stop-Ship Conditions

- Search crashes on malformed or changed transcript files.
- Public smoke eval fails.
- Private eval falls below Recall@5 90%.
- Private bench exceeds p95 250ms after repeat run.
- Raycast lint fails.
- Raycast build fails.
- README or launch copy claims semantic search or permanently stable local formats.
