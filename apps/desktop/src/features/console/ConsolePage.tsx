/**
 * Command console: the Phase 1 stand-in for chat. Every command is echoed with the
 * action it maps to, and the service answers honestly when a feature is not built yet.
 */
import type { CommandResult } from "@myai/api-client";
import { SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { Alert, Button, Input, PageHeader } from "../../components/ui";
import { describeError, useRunCommand } from "../../lib/api";

interface Entry {
  id: number;
  input: string;
  result?: CommandResult;
  error?: string;
}

const STARTERS = ["/help", "/status", "/hardware", "/skills", "teach yourself coding"];

export function ConsolePage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const run = useRunCommand();
  const navigate = useNavigate();
  const bottom = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => bottom.current?.scrollIntoView({ block: "end" }), [entries]);

  const submit = (input: string) => {
    const trimmed = input.trim();
    if (!trimmed) return;
    const id = nextId.current++;
    setEntries((e) => [...e, { id, input: trimmed }]);
    setText("");
    run.mutate(trimmed, {
      onSuccess: (result) => {
        setEntries((e) => e.map((x) => (x.id === id ? { ...x, result } : x)));
        const target = result.data["navigate"];
        if (typeof target === "string") void navigate(target);
      },
      onError: (error) => {
        setEntries((e) => e.map((x) => (x.id === id ? { ...x, error: describeError(error) } : x)));
      },
    });
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <PageHeader
        title="Console"
        subtitle="Talk to your AI with commands. Chat arrives once a local model is set up."
      />
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {entries.length === 0 && (
          <div className="rounded-card border border-dashed border-border p-6 text-sm text-fg-muted">
            <p>Try one of these:</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {STARTERS.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    submit(s);
                  }}
                >
                  {s}
                </Button>
              ))}
            </div>
          </div>
        )}
        {entries.map((e) => (
          <div key={e.id} className="animate-rise space-y-2">
            <div className="flex justify-end">
              <span className="rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm text-accent-fg">
                {e.input}
              </span>
            </div>
            {e.result ? <ResultBubble result={e.result} onSuggestion={submit} /> : null}
            {e.error ? <Alert tone="danger">{e.error}</Alert> : null}
            {!e.result && !e.error && <span className="text-xs text-fg-muted">…</span>}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form
        className="mt-4 flex gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          submit(text);
        }}
      >
        <Input
          aria-label="Command"
          placeholder="/help"
          value={text}
          onChange={(ev) => {
            setText(ev.target.value);
          }}
          autoFocus
          className="font-mono"
        />
        <Button type="submit" disabled={run.isPending || !text.trim()} aria-label="Send">
          <SendHorizontal className="h-4 w-4" aria-hidden />
        </Button>
      </form>
    </div>
  );
}

function ResultBubble({
  result,
  onSuggestion,
}: {
  result: CommandResult;
  onSuggestion: (s: string) => void;
}) {
  const tone = { ok: "success", unavailable: "warning", error: "danger" } as const;
  const cmd = result.command;
  return (
    <div className="max-w-2xl space-y-2">
      {cmd && (
        <div className="text-xs text-fg-muted">
          →{" "}
          <span className="font-mono">
            /{cmd.name}
            {cmd.args.length ? " " + cmd.args.join(" ") : ""}
          </span>
          {cmd.natural_language && " (mapped from your sentence)"}
        </div>
      )}
      <Alert tone={tone[result.outcome]} title={result.title}>
        <pre className="font-sans whitespace-pre-wrap">{result.message}</pre>
      </Alert>
      {result.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.suggestions.map((s) => (
            <Button
              key={s}
              size="sm"
              variant="secondary"
              onClick={() => {
                onSuggestion(s);
              }}
            >
              {s}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
