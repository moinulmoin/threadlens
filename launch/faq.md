# FAQ

## Is Threadlens a memory tool?

Not primarily. Threadlens is a search tool. Indexing is internal plumbing, and
resume/open commands are optional actions on search results.

## Does it upload transcripts?

No. V0 reads local session stores and writes a local SQLite cache. It does not
upload transcript content.

## What agents does it support?

Default sources:

- Codex local JSONL sessions.
- Claude Code local JSONL sessions.
- Cursor local records.
- Pi local JSONL sessions.
- OMP local JSONL sessions.
- Amp Code local prompt history.
- Droid local JSONL sessions.
- OpenCode local SQLite sessions when the database contains sessions.
- Custom JSONL sources.

## Which sources are most likely to drift?

Cursor and OpenCode use local formats that are less stable than the JSONL-backed
agents. Amp Code support depends on the local prompt-history file shape. These
adapters should fail per store/file if formats change, without breaking refresh
for the rest.

## Is it semantic search?

No, not in V0. V0 uses SQLite full-text search, prefix matching, and bounded
fuzzy fallback for typo tolerance.

This keeps the first version fast, local, explainable, and dependency-light.

## Why not use embeddings first?

Embeddings may be useful later, but they add model choice, privacy boundaries,
storage costs, and evaluation complexity. The first useful version should find
sessions from rough keywords and typos without needing a model.

## What happens if a transcript format changes?

Adapters should fail per file/source and continue refreshing the rest. The raw
agent session stores remain the source of truth, and the local cache can be
rebuilt.

## Can I add another agent?

Yes, if the agent writes JSONL or JSONL-like transcript records. Add a custom
source profile with:

- File glob.
- Session id field path.
- Message id field path.
- Role field path.
- Text field path.
- Timestamp field path.
- Optional cwd/title field paths.
- Optional resume command template.

## Does it run agent resume commands?

No. Threadlens prints or copies resume commands. The user decides whether to
run them.

## Why CLI first?

The CLI is the contract. It keeps parsing, indexing, ranking, and evals in one
place. Raycast can stay thin instead of becoming a second search engine.

## What is the reliability bar?

V0 should pass:

- Unit tests for adapters, CLI behavior, profile parsing, and ranking.
- Public custom-source smoke eval.
- Private local query-to-session eval with Recall@5 >= 90%.
- Query latency bench with p95 below 250ms on the local corpus.
- Raycast TypeScript build.
- Dependency audit.

## What should not be in V0?

- Hosted sync.
- Team sharing.
- Account system.
- Background daemon.
- Semantic embeddings.
- Claims that every agent format is stable forever.
