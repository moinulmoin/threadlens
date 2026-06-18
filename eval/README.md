# Threadlens Evaluation

The real acceptance test is a private local eval file with known session ids.
Do not commit the private file; it contains local paths and transcript-derived
queries.

Each case should target one known session, or a small set of equivalent
sessions when the same remembered work exists in multiple agents, and include:

- 5 positive queries that a user might actually remember.
- 2 negative queries from unrelated sessions.
- A mix of exact phrases, partial phrases, project names, identifiers, and typos.

Single-target shape:

```json
{
  "case_id": "monorepo_api_split",
  "target": {"source": "codex", "session_id": "known-session-id"},
  "queries": ["monorepo api split"],
  "negative_queries": ["plunk otp"]
}
```

Multi-target shape:

```json
{
  "case_id": "same_work_cross_agent",
  "targets": [
    {"source": "codex", "session_id": "known-session-id"},
    {"source": "omp", "session_id": "equivalent-session-id"}
  ],
  "queries": ["same remembered work"],
  "negative_queries": ["unrelated phrase"]
}
```

Good positive query examples:

- `monorepo api split`
- `PostHog OTP conversion rate`
- `VoiceAgentSessionController 8979`
- `hmm u are good my guy`

Bad eval queries are vague product demos such as `where did I do what`. The
system should be judged on whether it retrieves the right local coding-agent
session from remembered content.

Do not use a currently active Threadlens development session as an eval target
after printing eval reports into that same session. Those transcripts can contain
the positive and negative query labels verbatim, which makes the fixture
self-referential instead of measuring retrieval quality.

Run the private acceptance eval when `.threadlens/eval-local-10.json` exists:

```bash
threadlens --db .threadlens/index.sqlite eval .threadlens/eval-local-10.json
threadlens --db .threadlens/index.sqlite eval .threadlens/eval-local-10.json --timings
threadlens --db .threadlens/index.sqlite bench .threadlens/eval-local-10.json --max-p95-ms 250
```

V0 passes when Recall@5 is at least 90% and unrelated target sessions do not
appear in the top 5. The benchmark pass line is p95 query latency under 250ms
on the current local corpus.

For CI and public smoke testing, use the committed custom source fixture:

```bash
threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json sources add demoagent \
  --path eval/custom-source.example.jsonl \
  --session-key session.id \
  --message-key message.id \
  --role-key message.role \
  --text-key message.content \
  --timestamp-key createdAt \
  --cwd-key cwd \
  --title-key title
threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json refresh --source demoagent --force
threadlens --db /tmp/threadlens-smoke.sqlite --config /tmp/threadlens-sources.json eval eval/custom-source.eval.json
```
