# Launch Checklist

## Product Gates

- [ ] `README.md` states the V0 boundary clearly.
- [ ] `PLAN.md` matches actual commands and non-goals.
- [ ] Cursor/OpenCode format-drift caveats are described clearly.
- [ ] Public copy does not claim semantic search.
- [ ] Public copy does not claim universal agent support.
- [ ] Public copy does not expose private session snippets.
- [ ] Resume commands are described as optional copyable actions.
- [ ] Bundled Codex skill is packaged and discoverable with `threadlens skill`.
- [ ] `LICENSE` exists and package metadata points to it.
- [ ] Logo asset renders in README and launch surfaces.
- [ ] Release workflow builds Python package artifacts from a tag.

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
mkdir -p /private/tmp/threadlens-smoke
threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json sources add demoagent \
  --path eval/custom-source.example.jsonl \
  --session-key session.id \
  --message-key message.id \
  --role-key message.role \
  --text-key message.content \
  --timestamp-key createdAt \
  --cwd-key cwd \
  --title-key title \
  --resume-template "cd {cwd} && demoagent resume {session_id}"

threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json refresh --source demoagent --force
threadlens --db /private/tmp/threadlens-smoke/index.sqlite --config /private/tmp/threadlens-smoke/sources.json eval eval/custom-source.eval.json
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
- Unit tests: 47 passed, including bundled-skill coverage.
- `doctor --json`: passed.
- Installed CLI index: ready with 110,288 messages.
- Expanded source counts: Codex 26,992, Claude 2,116, Cursor 5, Pi 468, OMP
  53,660, Amp 83, Droid 26,960, OpenCode 4.
- OpenCode source: indexed 4 messages from 1 local session.
- New-source refresh: Pi, OMP, Amp, and Droid refreshed into the real user-level
  index.
- Source-restricted searches for Pi, OMP, Amp, and Droid returned results; Pi,
  OMP, and Droid include copyable resume commands while Amp currently does not
  expose resumable session ids.
- OpenCode source-restricted search returned the new local OpenCode session with
  a copyable `opencode --session` command.
- Private eval bench: p95 148.9ms, below the 250ms gate.
- `doctor --json` reports the index as ready and reports freshness separately;
  active Codex sessions can still show stale-file hints while the index remains
  usable.
- Legacy private eval fixture: not launch-valid after current Threadlens
  development sessions included eval labels verbatim; rebuild it with clean
  targets or multi-target equivalents before claiming Recall@5.
- Public custom-source eval: 5/5 positives, 0/2 negatives.
- Raycast TypeScript: passed.
- Raycast lint: passed.
- Raycast audit: 0 vulnerabilities.
- Raycast build: passed before this launch-prep/docs/package pass; Raycast source
  did not change in this pass.
- Project-scoped search: `--cwd` verified against the Threadlens repo.
- Raycast result primary action: copy resume command before details.
- Bundled skill command: `threadlens skill --json` added and verified from a
  temporary installed wheel.
- Python sdist and wheel build: passed; wheel includes `SKILL.md` and
  `agents/openai.yaml`.

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

- Search crashes on malformed or changed session files.
- Public smoke eval fails.
- Private eval falls below Recall@5 90%.
- Private bench exceeds p95 250ms after repeat run.
- Raycast lint fails.
- Raycast build fails.
- README or launch copy claims semantic search or permanently stable local formats.
