/**
 * Streaming chat with the local model. Every reply shows which knowledge passages were
 * retrieved and which model answered; failures are shown inline, never swallowed.
 */
import type { ConversationRead, MessageRead, RetrievedChunk } from "@myai/api-client";
import { MessageSquarePlus, Pencil, SendHorizontal, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { Alert, Button, Input, PhaseTag, Spinner } from "../../components/ui";
import {
  describeError,
  localAiKeys,
  streamChatTurn,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useMessages,
  useRenameConversation,
  useStatus,
} from "../../lib/api";
import { cx } from "../../lib/cx";
import { queryClient } from "../../lib/query";

interface LiveTurn {
  user: string;
  assistant: string;
  retrieved: RetrievedChunk[];
  modelId: string | null;
  error: string | null;
  command: { title: string; message: string } | null;
}

export function ChatPage() {
  const status = useStatus();
  const conversations = useConversations();
  const create = useCreateConversation();
  const remove = useDeleteConversation();
  const rename = useRenameConversation();
  const [selected, setSelected] = useState<string | null>(null);
  const [live, setLive] = useState<LiveTurn | null>(null);
  const [transient, setTransient] = useState<LiveTurn | null>(null);
  const [text, setText] = useState("");
  const abort = useRef<AbortController | null>(null);
  const messages = useMessages(selected);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.data, live]);

  const aiReady = status.data?.ai === "available";

  const select = (id: string | null) => {
    setSelected(id);
    setTransient(null);
  };

  const send = async (input: string) => {
    const content = input.trim();
    if (!content || live) return;
    let conversationId = selected;
    if (!conversationId) {
      const created = await create.mutateAsync(undefined);
      conversationId = created.id;
      setSelected(conversationId);
    }
    setText("");
    setTransient(null);
    const controller = new AbortController();
    abort.current = controller;
    const turn: LiveTurn = {
      user: content,
      assistant: "",
      retrieved: [],
      modelId: null,
      error: null,
      command: null,
    };
    setLive({ ...turn });
    try {
      for await (const event of streamChatTurn(conversationId, content, controller.signal)) {
        if (event.event === "meta") {
          const meta = event.data as { model_id: string; retrieved: RetrievedChunk[] };
          turn.modelId = meta.model_id;
          turn.retrieved = meta.retrieved;
        } else if (event.event === "delta") {
          turn.assistant += (event.data as { text: string }).text;
        } else if (event.event === "error") {
          turn.error = (event.data as { message: string }).message;
        } else if (event.event === "command") {
          const cmd = event.data as { title: string; message: string };
          turn.command = { title: cmd.title, message: cmd.message };
        }
        setLive({ ...turn });
      }
    } catch (error) {
      if (!controller.signal.aborted) turn.error = describeError(error);
    } finally {
      setLive(null);
      abort.current = null;
      void queryClient.invalidateQueries({ queryKey: localAiKeys.messages(conversationId) });
      void queryClient.invalidateQueries({ queryKey: localAiKeys.conversations });
      // Commands are not persisted as chat turns and a failed request leaves no reply
      // behind, so show those results once until the next action.
      if (turn.command || (turn.error && !turn.assistant)) setTransient(turn);
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-5">
      <aside className="flex w-60 shrink-0 flex-col">
        <Button
          variant="secondary"
          onClick={() => {
            select(null);
          }}
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden /> New conversation
        </Button>
        <ul className="mt-3 flex-1 space-y-1 overflow-y-auto">
          {conversations.data?.map((c) => (
            <ConversationItem
              key={c.id}
              conversation={c}
              active={c.id === selected}
              onSelect={() => {
                select(c.id);
              }}
              onDelete={() => {
                remove.mutate(c.id);
                if (selected === c.id) select(null);
              }}
              onRename={(title) => {
                rename.mutate({ conversation_id: c.id, title });
              }}
            />
          ))}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        {!aiReady && status.data && (
          <Alert
            tone={status.data.ai === "unavailable" ? "danger" : "warning"}
            title="Chat needs a local model"
          >
            {status.data.ai_detail}{" "}
            {status.data.ai === "not_configured" && (
              <Link to="/models" className="underline">
                Open Models
              </Link>
            )}
          </Alert>
        )}
        <div className="flex-1 space-y-4 overflow-y-auto py-4 pr-1">
          {messages.isPending && selected && <Spinner label="Loading conversation…" />}
          {messages.data?.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {live && (
            <>
              <Bubble role="user">{live.user}</Bubble>
              {live.command ? (
                <Alert tone="info" title={live.command.title}>
                  <pre className="font-sans whitespace-pre-wrap">{live.command.message}</pre>
                </Alert>
              ) : (
                <Bubble
                  role="assistant"
                  retrieved={live.retrieved}
                  modelId={live.modelId}
                  streaming
                >
                  {live.assistant || "…"}
                </Bubble>
              )}
              {live.error && <Alert tone="danger">{live.error}</Alert>}
            </>
          )}
          {transient && !live && (
            <>
              {transient.command && (
                <Alert tone="info" title={transient.command.title}>
                  <pre className="font-sans whitespace-pre-wrap">{transient.command.message}</pre>
                </Alert>
              )}
              {transient.error && <Alert tone="danger">{transient.error}</Alert>}
            </>
          )}
          {!selected && !live && (
            <div className="rounded-card border border-dashed border-border p-6 text-sm text-fg-muted">
              <p>
                Start a conversation. Your AI answers with the active local model, using what you
                have added to Memory and Knowledge. Slash commands like{" "}
                <code className="font-mono">/memory</code> work here too.
              </p>
              <p className="mt-2 flex items-center gap-2">
                <PhaseTag phase={2} /> Retrieval is lexical (keyword) search; semantic search is
                planned.
              </p>
            </div>
          )}
          <div ref={bottom} />
        </div>
        <form
          className="flex gap-2 border-t border-border pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send(text);
          }}
        >
          <Input
            aria-label="Message"
            placeholder={aiReady ? "Message your AI…" : "Set up a model first"}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
            }}
            disabled={!aiReady || !!live}
            autoFocus
          />
          {live ? (
            <Button
              type="button"
              variant="secondary"
              onClick={() => abort.current?.abort()}
              aria-label="Stop"
            >
              <Square className="h-4 w-4" aria-hidden />
            </Button>
          ) : (
            <Button type="submit" disabled={!aiReady || !text.trim()} aria-label="Send">
              <SendHorizontal className="h-4 w-4" aria-hidden />
            </Button>
          )}
        </form>
      </section>
    </div>
  );
}

function ConversationItem({
  conversation,
  active,
  onSelect,
  onDelete,
  onRename,
}: {
  conversation: ConversationRead;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conversation.title);
  const commit = () => {
    const title = draft.trim();
    setEditing(false);
    if (title && title !== conversation.title) onRename(title);
    else setDraft(conversation.title);
  };
  return (
    <li
      className={cx(
        "group flex items-center rounded-xl",
        active ? "bg-accent-soft" : "hover:bg-bg-muted",
      )}
    >
      {editing ? (
        <input
          aria-label="Conversation title"
          className="min-w-0 flex-1 rounded-lg border border-accent bg-bg px-2 py-1 text-sm outline-none"
          value={draft}
          maxLength={200}
          autoFocus
          onChange={(e) => {
            setDraft(e.target.value);
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setDraft(conversation.title);
              setEditing(false);
            }
          }}
        />
      ) : (
        <button
          type="button"
          onClick={onSelect}
          onDoubleClick={() => {
            setEditing(true);
          }}
          className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm"
        >
          {conversation.title}
        </button>
      )}
      <button
        type="button"
        aria-label={`Rename ${conversation.title}`}
        onClick={() => {
          setDraft(conversation.title);
          setEditing(true);
        }}
        className="rounded-md p-1 text-fg-muted opacity-0 group-hover:opacity-100 hover:text-fg"
      >
        <Pencil className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={`Delete ${conversation.title}`}
        onClick={onDelete}
        className="mr-1 rounded-md p-1 text-fg-muted opacity-0 group-hover:opacity-100 hover:text-danger"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden />
      </button>
    </li>
  );
}

function MessageBubble({ message }: { message: MessageRead }) {
  if (message.role === "user") return <Bubble role="user">{message.content}</Bubble>;
  return (
    <Bubble
      role="assistant"
      modelId={message.model_id}
      retrievedCount={message.retrieved_chunk_ids.length}
    >
      {message.content}
      {message.finish_reason === "error" && (
        <div className="mt-2 text-xs text-danger">This reply was interrupted by an error.</div>
      )}
      {message.duration_ms != null && (
        <div className="mt-1 text-[10px] text-fg-muted">
          {message.duration_ms} ms
          {message.completion_tokens ? ` · ${message.completion_tokens} tokens` : ""}
        </div>
      )}
    </Bubble>
  );
}

function Bubble({
  role,
  children,
  retrieved,
  retrievedCount,
  modelId,
  streaming,
}: {
  role: "user" | "assistant";
  children: React.ReactNode;
  retrieved?: RetrievedChunk[];
  retrievedCount?: number;
  modelId?: string | null;
  streaming?: boolean;
}) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm whitespace-pre-wrap text-accent-fg">
          {children}
        </div>
      </div>
    );
  }
  const sources =
    retrieved && retrieved.length > 0 ? [...new Set(retrieved.map((r) => r.document_title))] : [];
  return (
    <div className="max-w-[85%]">
      <div
        className={cx(
          "rounded-2xl rounded-bl-sm border border-border bg-bg-elevated px-4 py-2 text-sm whitespace-pre-wrap",
          streaming && "animate-pulse-soft",
        )}
      >
        {children}
      </div>
      <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-fg-muted">
        {modelId && <span>{modelId}</span>}
        {sources.length > 0 && <span>using: {sources.join(", ")}</span>}
        {retrievedCount ? <span>{retrievedCount} knowledge passages used</span> : null}
      </div>
    </div>
  );
}
