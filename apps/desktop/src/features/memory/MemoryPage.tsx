import type { MemoryCategory, MemoryRead } from "@myai/api-client";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  Alert,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Spinner,
} from "../../components/ui";
import {
  describeError,
  useAddMemory,
  useClearMemories,
  useDeleteMemory,
  useMemories,
  useUpdateMemory,
} from "../../lib/api";

const CATEGORIES: MemoryCategory[] = ["fact", "preference", "instruction", "other"];

export function MemoryPage() {
  const [query, setQuery] = useState("");
  const memories = useMemories(query);
  const add = useAddMemory();
  const update = useUpdateMemory();
  const remove = useDeleteMemory();
  const clear = useClearMemories();
  const [content, setContent] = useState("");
  const [category, setCategory] = useState<MemoryCategory>("fact");

  return (
    <>
      <PageHeader
        title="Memory"
        subtitle="What your AI remembers about you. Only what you add here; conversations are never remembered automatically."
        action={
          <Button
            variant="danger"
            size="sm"
            disabled={!memories.data?.length}
            onClick={() => {
              if (window.confirm("Delete every memory? This cannot be undone.")) clear.mutate();
            }}
          >
            Clear all
          </Button>
        }
      />
      <Card title="Remember something new">
        <form
          className="grid gap-3 md:grid-cols-[1fr_10rem_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!content.trim()) return;
            add.mutate(
              { content: content.trim(), category },
              {
                onSuccess: () => {
                  setContent("");
                },
              },
            );
          }}
        >
          <Field label="Memory" htmlFor="memory-content">
            <Input
              id="memory-content"
              value={content}
              maxLength={1000}
              onChange={(e) => {
                setContent(e.target.value);
              }}
              placeholder="Alex prefers concise answers"
            />
          </Field>
          <Field label="Category" htmlFor="memory-category">
            <select
              id="memory-category"
              className="h-10 w-full rounded-xl border border-border bg-bg px-3 text-sm"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value as MemoryCategory);
              }}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={add.isPending || !content.trim()}>
              Remember
            </Button>
          </div>
        </form>
        {add.isError && (
          <div className="mt-3">
            <Alert tone="danger">{describeError(add.error)}</Alert>
          </div>
        )}
      </Card>

      <div className="mt-5">
        <Input
          aria-label="Search memories"
          placeholder="Search memories…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
          }}
        />
      </div>
      <Card className="mt-3">
        {memories.isPending && <Spinner />}
        {memories.isError && <Alert tone="danger">{describeError(memories.error)}</Alert>}
        {memories.data && memories.data.length === 0 && (
          <EmptyState icon="🧠" title={query ? "No matching memories" : "Nothing remembered yet"}>
            Memories are included in every conversation so your AI can use them.
          </EmptyState>
        )}
        <ul className="divide-y divide-border">
          {memories.data?.map((m) => (
            <MemoryRow
              key={m.id}
              memory={m}
              onDelete={() => {
                remove.mutate(m.id);
              }}
              onSave={(text) => {
                update.mutate({
                  memory_id: m.id,
                  body: { content: text, expected_version: m.version },
                });
              }}
            />
          ))}
        </ul>
        {update.isError && <Alert tone="danger">{describeError(update.error)}</Alert>}
      </Card>
    </>
  );
}

function MemoryRow({
  memory,
  onDelete,
  onSave,
}: {
  memory: MemoryRead;
  onDelete: () => void;
  onSave: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memory.content);
  return (
    <li className="flex items-start gap-3 py-3 text-sm">
      <span className="mt-0.5 w-24 shrink-0 rounded-md bg-bg-muted px-2 py-0.5 text-center text-xs">
        {memory.category}
      </span>
      {editing ? (
        <form
          className="flex flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(draft.trim());
            setEditing(false);
          }}
        >
          <Input
            aria-label="Edit memory"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
            }}
            autoFocus
          />
          <Button size="sm" type="submit">
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            type="button"
            onClick={() => {
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        </form>
      ) : (
        <>
          <span className="flex-1">{memory.content}</span>
          <Button
            size="sm"
            variant="ghost"
            aria-label="Edit"
            onClick={() => {
              setEditing(true);
            }}
          >
            <Pencil className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button size="sm" variant="ghost" aria-label="Delete" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </>
      )}
    </li>
  );
}
