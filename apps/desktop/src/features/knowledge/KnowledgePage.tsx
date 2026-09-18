import { formatBytes } from "@myai/api-client";
import { FilePlus2, Search, Trash2 } from "lucide-react";
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
  useAddKnowledgeFile,
  useAddKnowledgeText,
  useDeleteDocument,
  useKnowledge,
  useKnowledgeSearch,
} from "../../lib/api";
import { inTauri } from "../../lib/tauri";

export function KnowledgePage() {
  const knowledge = useKnowledge();
  const addFile = useAddKnowledgeFile();
  const addText = useAddKnowledgeText();
  const remove = useDeleteDocument();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const search = useKnowledgeSearch(submitted);
  const [pathInput, setPathInput] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [errors, setErrors] = useState<string[]>([]);

  const pickFiles = async () => {
    if (!inTauri) {
      if (pathInput.trim())
        addFile.mutate(
          { path: pathInput.trim() },
          {
            onError: (e) => {
              setErrors((x) => [...x, describeError(e)]);
            },
          },
        );
      return;
    }
    const { open } = await import("@tauri-apps/plugin-dialog");
    const chosen = await open({
      multiple: true,
      title: "Add documents to knowledge",
      filters: [
        {
          name: "Documents",
          extensions: (knowledge.data?.supported_suffixes ?? []).map((s) => s.slice(1)),
        },
      ],
    });
    const paths = Array.isArray(chosen) ? chosen : chosen ? [chosen] : [];
    setErrors([]);
    for (const p of paths) {
      try {
        await addFile.mutateAsync({ path: p });
      } catch (e) {
        setErrors((x) => [...x, `${p}: ${describeError(e)}`]);
      }
    }
  };

  return (
    <>
      <PageHeader
        title="Knowledge"
        subtitle="Documents your AI can look things up in. Knowledge gives it information to retrieve; it does not retrain the model."
      />
      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Add files">
          <p className="text-sm text-fg-muted">
            Supported: {knowledge.data?.supported_suffixes.join(", ") ?? "…"}. Files stay where they
            are; the text is indexed locally.
          </p>
          {!inTauri && (
            <div className="mt-3">
              <Input
                aria-label="File path"
                placeholder="/absolute/path/to/file.md"
                value={pathInput}
                onChange={(e) => {
                  setPathInput(e.target.value);
                }}
                className="font-mono"
              />
            </div>
          )}
          <Button className="mt-3" onClick={() => void pickFiles()} disabled={addFile.isPending}>
            <FilePlus2 className="h-4 w-4" aria-hidden />{" "}
            {addFile.isPending ? "Indexing…" : inTauri ? "Choose files…" : "Add path"}
          </Button>
          {errors.map((e) => (
            <div key={e} className="mt-2">
              <Alert tone="danger">{e}</Alert>
            </div>
          ))}
        </Card>
        <Card title="Add text">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              addText.mutate(
                { title: title.trim(), text },
                {
                  onSuccess: () => {
                    setTitle("");
                    setText("");
                  },
                },
              );
            }}
          >
            <Field label="Title" htmlFor="k-title">
              <Input
                id="k-title"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                }}
                maxLength={255}
              />
            </Field>
            <Field label="Text" htmlFor="k-text">
              <textarea
                id="k-text"
                className="min-h-24 w-full rounded border border-border bg-bg px-3 py-2 text-sm"
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                }}
              />
            </Field>
            <Button type="submit" disabled={addText.isPending || !title.trim() || !text.trim()}>
              Add
            </Button>
            {addText.isError && <Alert tone="danger">{describeError(addText.error)}</Alert>}
          </form>
        </Card>
      </div>

      <Card className="mt-5" title="Try a question">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(query);
          }}
        >
          <Input
            aria-label="Search knowledge"
            placeholder="What would your AI find for…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
            }}
          />
          <Button type="submit" variant="secondary">
            <Search className="h-4 w-4" aria-hidden /> Preview
          </Button>
        </form>
        <p className="mt-2 text-xs text-fg-muted">{knowledge.data?.retrieval_method}</p>
        {search.isFetching && <Spinner />}
        {search.data && search.data.length === 0 && (
          <p className="mt-3 text-sm text-fg-muted">No matching passages.</p>
        )}
        <ul className="mt-3 space-y-2">
          {search.data?.map((hit) => (
            <li key={hit.chunk_id} className="rounded bg-bg-muted p-3 text-sm">
              <div className="mb-1 text-xs font-semibold text-fg-muted">
                {hit.document_title} §{hit.ordinal + 1}
              </div>
              <p className="whitespace-pre-wrap">{hit.content}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card
        className="mt-5"
        title={`Library · ${knowledge.data?.document_count ?? 0} documents, ${knowledge.data?.chunk_count ?? 0} passages`}
      >
        {knowledge.isPending && <Spinner />}
        {knowledge.isError && <Alert tone="danger">{describeError(knowledge.error)}</Alert>}
        {knowledge.data && knowledge.data.documents.length === 0 && (
          <EmptyState icon="📚" title="No documents yet">
            Add notes, PDFs or code and your AI can cite them.
          </EmptyState>
        )}
        <ul className="divide-y divide-border">
          {knowledge.data?.documents.map((d) => (
            <li key={d.id} className="flex items-center gap-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
              <span className="text-xs text-fg-muted">{d.media_type}</span>
              <span className="w-16 text-right text-xs text-fg-muted">
                {formatBytes(d.size_bytes)}
              </span>
              <span className="w-20 text-right text-xs text-fg-muted">
                {d.chunk_count} passages
              </span>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Remove ${d.title}`}
                onClick={() => {
                  remove.mutate(d.id);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
