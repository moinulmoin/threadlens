import {
  Action,
  ActionPanel,
  Clipboard,
  List,
  showToast,
  Toast,
  getPreferenceValues,
} from "@raycast/api";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { useEffect, useState } from "react";

const execFileAsync = promisify(execFile);

type Preferences = {
  threadlensCommand: string;
  threadlensArgs?: string;
  threadlensCwd?: string;
};

type ThreadlensSnippet = {
  role: string;
  timestamp: string;
  snippet: string;
  match_type?: string;
};

type ThreadlensResult = {
  result_id: string;
  source: string;
  session_id: string;
  cwd: string;
  title: string;
  last_timestamp: string;
  score: number;
  matched_terms: string[];
  best_snippets: ThreadlensSnippet[];
  source_path: string;
  source_line: number;
  actions?: {
    resume_command?: string;
    open_source?: string;
  };
};

export default function Command() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ThreadlensResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    let isCurrent = true;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const nextResults = await searchThreadlens(query, controller.signal);
        if (isCurrent) {
          setResults(nextResults);
        }
      } catch (error) {
        if (!isCurrent || isAbortError(error)) {
          return;
        }
        setResults([]);
        await showToast({
          style: Toast.Style.Failure,
          title: "Threadlens search failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    }, 180);

    return () => {
      isCurrent = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <List
      isLoading={isLoading}
      isShowingDetail
      onSearchTextChange={setQuery}
      searchBarPlaceholder="Search local coding-agent sessions..."
      throttle
    >
      {results.map((result) => (
        <List.Item
          key={result.result_id}
          title={result.title || result.session_id}
          subtitle={result.cwd || result.source}
          accessories={[
            { text: result.source },
            {
              text: result.last_timestamp
                ? result.last_timestamp.slice(0, 10)
                : "",
            },
            { text: String(Math.round(result.score)) },
          ]}
          detail={
            <List.Item.Detail
              markdown={result.best_snippets
                .map(
                  (snippet) =>
                    `**${escapeMarkdown(snippet.role)}** ${escapeMarkdown(snippet.timestamp)}\n\n${escapeMarkdown(
                      snippet.snippet,
                    )}`,
                )
                .join("\n\n---\n\n")}
            />
          }
          actions={<ThreadlensActions result={result} />}
        />
      ))}
    </List>
  );
}

function ThreadlensActions({ result }: { result: ThreadlensResult }) {
  return (
    <ActionPanel>
      {result.actions?.resume_command ? (
        <Action.CopyToClipboard
          title="Copy Resume Command"
          content={result.actions.resume_command}
        />
      ) : null}
      <Action
        title="Copy Session Brief"
        onAction={() => copyBrief(result.result_id)}
      />
      <Action.CopyToClipboard
        title="Copy Result ID"
        content={result.result_id}
      />
      <Action.CopyToClipboard
        title="Copy Source Path"
        content={result.actions?.open_source || result.source_path}
      />
      <Action.Open title="Open Source File" target={result.source_path} />
    </ActionPanel>
  );
}

async function searchThreadlens(
  query: string,
  signal: AbortSignal,
): Promise<ThreadlensResult[]> {
  const { stdout } = await runThreadlens(
    ["search", query, "--json", "--no-bootstrap"],
    signal,
  );
  return parseThreadlensResults(stdout);
}

async function copyBrief(resultId: string) {
  try {
    const { stdout } = await runThreadlens(["brief", resultId, "--json"]);
    await Clipboard.copy(stdout.trim());
    await showToast({
      style: Toast.Style.Success,
      title: "Copied session brief",
    });
  } catch (error) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Could not copy brief",
      message: error instanceof Error ? error.message : String(error),
    });
  }
}

async function runThreadlens(args: string[], signal?: AbortSignal) {
  const preferences = getPreferenceValues<Preferences>();
  const command = preferences.threadlensCommand || "threadlens";
  const baseArgs = splitArgs(preferences.threadlensArgs || "");
  return execFileAsync(command, [...baseArgs, ...args], {
    cwd: preferences.threadlensCwd || undefined,
    signal,
    timeout: 10_000,
    maxBuffer: 1024 * 1024 * 4,
  });
}

function splitArgs(value: string): string[] {
  const matches = value.match(/(?:[^\s"]+|"[^"]*")+/g) || [];
  return matches.map((part) => part.replace(/^"|"$/g, ""));
}

function parseThreadlensResults(stdout: string): ThreadlensResult[] {
  const results: ThreadlensResult[] = [];
  let malformedLines = 0;

  for (const line of stdout.split("\n")) {
    const trimmedLine = line.trim();
    if (!trimmedLine) {
      continue;
    }

    try {
      results.push(JSON.parse(trimmedLine) as ThreadlensResult);
    } catch {
      malformedLines += 1;
    }
  }

  if (malformedLines > 0 && results.length === 0) {
    throw new Error("Threadlens returned malformed JSONL");
  }

  return results;
}

function escapeMarkdown(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/([`*_{}[\]()#+\-.!|])/g, "\\$1");
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}
