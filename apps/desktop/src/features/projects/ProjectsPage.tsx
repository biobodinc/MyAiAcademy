import { Archive, ArchiveRestore, FolderKanban, Trash2 } from "lucide-react";
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
  useArchiveProject,
  useCreateProject,
  useDeleteProject,
  useProjectContents,
  useProjects,
} from "../../lib/api";

export function ProjectsPage() {
  const [showArchived, setShowArchived] = useState(false);
  const projects = useProjects(showArchived);
  const create = useCreateProject();
  const archive = useArchiveProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="Group the conversations, memories and files that belong to one piece of work. Nothing has to be in a project."
        action={
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setShowArchived((v) => !v);
            }}
          >
            {showArchived ? "Hide archived" : "Show archived"}
          </Button>
        }
      />

      <Card title="Start a project">
        <form
          className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return;
            create.mutate(
              { name: name.trim(), description: description.trim() },
              {
                onSuccess: () => {
                  setName("");
                  setDescription("");
                },
              },
            );
          }}
        >
          <Field label="Name">
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
              placeholder="Kitchen rebuild"
            />
          </Field>
          <Field label="Description">
            <Input
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
              }}
              placeholder="Optional"
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              Create
            </Button>
          </div>
        </form>
        {create.error ? <Alert tone="danger">{describeError(create.error)}</Alert> : null}
      </Card>

      {projects.isLoading ? <Spinner /> : null}
      {projects.error ? <Alert tone="danger">{describeError(projects.error)}</Alert> : null}

      {projects.data?.length === 0 ? (
        <EmptyState icon={<FolderKanban size={20} />} title="No projects yet">
          A project is a label, not a folder. Everything works perfectly well without one — a
          project just makes it easier to find the work that belongs together.
        </EmptyState>
      ) : null}

      <div className="grid gap-3">
        {projects.data?.map((project) => (
          <Card key={project.id} title={project.name}>
            {project.description ? (
              <p className="text-sm text-muted">{project.description}</p>
            ) : null}
            {project.archived ? <p className="text-sm text-muted">Archived.</p> : null}

            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  archive.mutate({ project_id: project.id, archived: !project.archived });
                }}
              >
                {project.archived ? (
                  <>
                    <ArchiveRestore size={14} /> Restore
                  </>
                ) : (
                  <>
                    <Archive size={14} /> Archive
                  </>
                )}
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => {
                  setConfirming(confirming === project.id ? null : project.id);
                }}
              >
                <Trash2 size={14} /> Delete
              </Button>
            </div>

            {confirming === project.id ? (
              <DeleteChoice
                projectId={project.id}
                onDone={() => {
                  setConfirming(null);
                }}
              />
            ) : null}
          </Card>
        ))}
      </div>
    </>
  );
}

/**
 * The delete question, asked properly.
 *
 * Two buttons rather than a checkbox and one: a checkbox has a default state, and the
 * default would decide for everyone who did not read it. Here neither answer is pre-selected,
 * each says what it does to the contents, and the counts are real — fetched before the
 * question is asked, so "and its 14 items" is a fact rather than a warning shape.
 */
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function DeleteChoice({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const contents = useProjectContents(projectId);
  const remove = useDeleteProject();

  if (contents.isLoading) return <Spinner />;
  const held = contents.data;
  if (!held) return null;

  const act = (choice: "keep" | "delete") => {
    remove.mutate({ project_id: projectId, contents: choice }, { onSuccess: onDone });
  };

  return (
    <div className="mt-3 rounded border border-danger/40 p-3">
      {held.total === 0 ? (
        <p className="text-sm">Nothing is filed under this project.</p>
      ) : (
        <p className="text-sm">
          {plural(held.conversations, "conversation")},{" "}
          {plural(held.memories, "memory", "memories")} and {plural(held.documents, "document")} are
          filed here. What should happen to them?
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={remove.isPending}
          onClick={() => {
            act("keep");
          }}
        >
          Delete the project, keep the {plural(held.total, "item")}
        </Button>
        <Button
          size="sm"
          variant="danger"
          disabled={remove.isPending}
          onClick={() => {
            act("delete");
          }}
        >
          Delete the project and everything in it
        </Button>
        <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={onDone}>
          Cancel
        </Button>
      </div>
      {remove.error ? <Alert tone="danger">{describeError(remove.error)}</Alert> : null}
    </div>
  );
}
