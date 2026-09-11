/**
 * The built-in onboarding guide (spec §66). Deterministic answers about MyAI Academy
 * itself; every answer is labelled so it is never mistaken for the user's AI model.
 */
import type { GuideAnswer } from "@myai/api-client";
import { HelpCircle, SendHorizontal } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Input } from "../../components/ui";
import { describeError, useAskGuide, useGuideTopics } from "../../lib/api";

export function GuidePanel({ compact = false }: { compact?: boolean }) {
  const topics = useGuideTopics();
  const ask = useAskGuide();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<GuideAnswer | null>(null);

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    ask.mutate(trimmed, { onSuccess: setAnswer });
  };

  const suggestions = (answer?.related.length ? answer.related : (topics.data ?? [])).slice(
    0,
    compact ? 3 : 5,
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <HelpCircle className="h-4 w-4 text-accent" aria-hidden />
        Questions about MyAI Academy?
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <Input
          aria-label="Ask the guide"
          placeholder="What is training?"
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
          }}
        />
        <Button type="submit" disabled={ask.isPending || !question.trim()} aria-label="Ask">
          <SendHorizontal className="h-4 w-4" aria-hidden />
        </Button>
      </form>
      {ask.isError && <Alert tone="danger">{describeError(ask.error)}</Alert>}
      {answer && (
        <Alert tone={answer.matched ? "info" : "warning"} title={answer.title}>
          <p>{answer.answer}</p>
          <p className="mt-2 text-xs text-fg-muted">{answer.source}</p>
        </Alert>
      )}
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((t) => (
            <Button
              key={t.id}
              size="sm"
              variant="secondary"
              onClick={() => {
                setQuestion(t.question);
                submit(t.question);
              }}
            >
              {t.question}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
