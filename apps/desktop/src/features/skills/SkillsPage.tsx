/**
 * Skills (spec §33-§36, §42-§43, §82-§83). Levels are shown exactly as the benchmark set
 * them; learning shows a preview, needs a confirmation, and reports the running job.
 */
import {
  BAND_LABELS,
  formatBytes,
  titleCase,
  type AchievementStatus,
  type DegreeStatus,
  type EvaluationRead,
  type JobRead,
  type LearnPreview,
  type SkillStatus,
  type TrainingRunRead,
  type TrainPreview,
  type TrainRequest,
} from "@myai/api-client";
import { Dumbbell, GraduationCap, Lock, Pause, Play, RotateCcw, Square, Undo2 } from "lucide-react";
import { useState } from "react";

import {
  Alert,
  Button,
  Card,
  LevelBadge,
  PageHeader,
  PhaseTag,
  ProgressBar,
  Row,
  Spinner,
  StatusPill,
} from "../../components/ui";
import {
  describeError,
  useCurrentJob,
  useEvaluations,
  useJobAction,
  useLearnPreview,
  useRevertTraining,
  useSkillHistory,
  useSkills,
  useStartEvaluate,
  useStartLearn,
  useStartTrain,
  useTrainingRuns,
  useTrainPreview,
} from "../../lib/api";

const DOMAIN_ORDER = ["core", "creative", "technical", "knowledge"] as const;

export function SkillsPage() {
  const skills = useSkills();
  const job = useCurrentJob();
  const [previewFor, setPreviewFor] = useState<string | null>(null);
  const [trainFor, setTrainFor] = useState<string | null>(null);
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const evaluate = useStartEvaluate();

  if (skills.isPending) return <Spinner />;
  if (skills.isError) return <Alert tone="danger">{describeError(skills.error)}</Alert>;

  const groups = DOMAIN_ORDER.map((d) => ({
    domain: d,
    items: skills.data.skills.filter((s) => s.domain === d),
  })).filter((g) => g.items.length > 0);

  return (
    <>
      <PageHeader
        title="Skills"
        subtitle="Levels only change after a benchmark run with your local model. Nothing here is awarded for time spent."
        action={
          <div className="flex items-center gap-2 text-sm">
            Overall <LevelBadge level={skills.data.overall_level} />
          </div>
        }
      />
      {job.data && <JobCard job={job.data} />}
      {evaluate.isError && (
        <div className="mb-4">
          <Alert tone="danger">{describeError(evaluate.error)}</Alert>
        </div>
      )}
      <div className="space-y-6">
        {groups.map((g) => (
          <section key={g.domain}>
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-fg-muted uppercase">
              {titleCase(g.domain)}
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {g.items.map((s) => (
                <SkillCard
                  key={s.id}
                  skill={s}
                  busy={!!job.data}
                  onLearn={() => {
                    setPreviewFor(s.id);
                  }}
                  onEvaluate={() => {
                    evaluate.mutate(s.id);
                  }}
                  onHistory={() => {
                    setHistoryFor(s.id);
                  }}
                  onTrain={() => {
                    setTrainFor(s.id);
                  }}
                />
              ))}
            </div>
          </section>
        ))}
        <div className="grid gap-3 md:grid-cols-2">
          <DegreesCard degrees={skills.data.degrees} />
          <AchievementsCard achievements={skills.data.achievements} />
        </div>
        <HistoryCard />
      </div>
      {previewFor && (
        <LearnDialog
          skillId={previewFor}
          onClose={() => {
            setPreviewFor(null);
          }}
        />
      )}
      {trainFor && (
        <TrainDialog
          skillId={trainFor}
          onClose={() => {
            setTrainFor(null);
          }}
        />
      )}
      {historyFor && (
        <EvaluationsDialog
          skillId={historyFor}
          onClose={() => {
            setHistoryFor(null);
          }}
        />
      )}
    </>
  );
}

function SkillCard({
  skill,
  busy,
  onLearn,
  onEvaluate,
  onHistory,
  onTrain,
}: {
  skill: SkillStatus;
  busy: boolean;
  onLearn: () => void;
  onEvaluate: () => void;
  onHistory: () => void;
  onTrain: () => void;
}) {
  const areas = Object.entries(skill.area_scores);
  const revert = useRevertTraining();
  return (
    <Card className={skill.locked ? "opacity-70" : undefined}>
      <div className="flex items-start gap-3">
        <div className="text-3xl" aria-hidden>
          {skill.icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{skill.name}</h3>
            {skill.locked && <Lock className="h-3.5 w-3.5 text-fg-muted" aria-label="Locked" />}
            {!skill.learnable && <PhaseTag phase={skill.planned_phase} />}
            {skill.learned && <StatusPill tone="success">Learned</StatusPill>}
            {skill.trained_at && <StatusPill tone="info">Trained</StatusPill>}
          </div>
          <p className="text-sm text-fg-muted">{skill.description}</p>
          <div className="mt-3 flex items-center gap-3">
            <LevelBadge level={skill.level} size="sm" />
            <div className="flex-1">
              <ProgressBar value={skill.level} max={100} label={`${skill.name} level`} />
            </div>
            <span className="text-xs text-fg-muted">{BAND_LABELS[skill.band] ?? skill.band}</span>
          </div>
          {areas.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1">
              {areas.map(([area, score]) => (
                <li
                  key={area}
                  className="rounded-md bg-bg-muted px-2 py-0.5 text-xs text-fg-muted tabular-nums"
                >
                  {titleCase(area)} {Math.round(score * 100)}%
                </li>
              ))}
            </ul>
          )}
          {skill.trained_at && (
            <p className="mt-2 text-xs text-fg-muted">
              Trained on {new Date(skill.trained_at).toLocaleDateString()}: this skill uses
              instructions training measured as better. Undoing puts the package\u2019s own back and
              leaves the level as it was measured.
            </p>
          )}
          {skill.locked_reason && (
            <p className="mt-2 text-xs text-warning">{skill.locked_reason}</p>
          )}
          {!skill.learnable && (
            <p className="mt-2 text-xs text-fg-muted">
              No measurable benchmark exists for this skill yet, so it cannot be learned in this
              build.
            </p>
          )}
          {skill.package && !skill.learned && (
            <p className="mt-2 text-xs text-fg-muted">
              Package v{skill.package.version}: {skill.package.task_count} benchmark tasks across{" "}
              {skill.package.areas.map(titleCase).join(", ")} · {skill.package.license}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {skill.learnable && !skill.learned && (
              <Button size="sm" onClick={onLearn} disabled={skill.locked || busy}>
                <GraduationCap className="h-4 w-4" aria-hidden /> Learn
              </Button>
            )}
            {skill.learned && (
              <>
                {skill.trainable && (
                  <Button size="sm" onClick={onTrain} disabled={busy}>
                    <Dumbbell className="h-4 w-4" aria-hidden /> Train
                  </Button>
                )}
                <Button size="sm" variant="secondary" onClick={onEvaluate} disabled={busy}>
                  <RotateCcw className="h-4 w-4" aria-hidden /> Re-run benchmark
                </Button>
                <Button size="sm" variant="ghost" onClick={onHistory}>
                  History
                </Button>
                {skill.trained_at && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy || revert.isPending}
                    onClick={() => {
                      revert.mutate(skill.id);
                    }}
                  >
                    <Undo2 className="h-4 w-4" aria-hidden /> Undo training
                  </Button>
                )}
              </>
            )}
          </div>
          <ul className="mt-3 flex flex-wrap gap-1">
            {skill.specializations.map((sp) => (
              <li key={sp} className="rounded-md bg-bg-muted px-2 py-0.5 text-xs text-fg-muted">
                {sp}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

function JobCard({ job }: { job: JobRead }) {
  const act = useJobAction();
  const total = job.progress_total || 0;
  const pct = total ? Math.round((job.progress_done / total) * 100) : 0;
  const verb =
    job.kind === "learn" ? "Learning" : job.kind === "evaluate" ? "Evaluating" : "Training";
  return (
    <div className="mb-5">
      <Card title={`${verb} ${titleCase(job.skill_id)}`}>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <ProgressBar value={pct} label={`${verb} progress`} tone="accent" />
            <div className="mt-1 text-xs text-fg-muted">
              {job.status}
              {job.status === "paused" ? "" : "…"} · {job.kind === "train" ? "round" : "task"}{" "}
              {job.progress_done} of {total}
              {job.kind === "train" ? " (estimated)" : ""}
              {job.model_id ? ` · ${job.model_id}` : ""}
            </div>
          </div>
          {job.status === "paused" ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                act.mutate({ job_id: job.id, action: "resume" });
              }}
              aria-label="Resume"
            >
              <Play className="h-4 w-4" aria-hidden /> Resume
            </Button>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                act.mutate({ job_id: job.id, action: "pause" });
              }}
              aria-label="Pause"
            >
              <Pause className="h-4 w-4" aria-hidden /> Pause
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              act.mutate({ job_id: job.id, action: "cancel" });
            }}
            aria-label="Stop"
          >
            <Square className="h-4 w-4" aria-hidden /> Stop
          </Button>
        </div>
        <p className="mt-2 text-xs text-fg-muted">
          {job.kind === "train"
            ? "Each change is kept only if it measures better, and the benchmark at the end decides whether the result is kept at all. Stopping leaves the skill as it was."
            : "The skill counts as learned only when the benchmark finishes. Stopping leaves it as it was."}
        </p>
        {act.isError && (
          <div className="mt-2">
            <Alert tone="danger">{describeError(act.error)}</Alert>
          </div>
        )}
      </Card>
    </div>
  );
}

function LearnDialog({ skillId, onClose }: { skillId: string; onClose: () => void }) {
  const preview = useLearnPreview(skillId);
  const start = useStartLearn();
  const p: LearnPreview | undefined = preview.data;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="learn-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
    >
      <div className="w-full max-w-lg rounded-card border border-border bg-bg-elevated p-6 shadow-card">
        {preview.isPending && <Spinner />}
        {preview.isError && <Alert tone="danger">{describeError(preview.error)}</Alert>}
        {p && (
          <>
            <h2 id="learn-title" className="text-lg font-bold">
              {p.icon} New skill: {p.name}
            </h2>
            <p className="mt-2 text-sm">{p.what_happens}</p>
            {p.package && (
              <dl className="mt-4 space-y-1 text-sm">
                <Row label="Resources">
                  {formatBytes(p.package.size_bytes)} · {p.package.resources}
                </Row>
                <Row label="Benchmark">
                  {p.package.task_count} tasks across {p.package.areas.map(titleCase).join(", ")}
                </Row>
                <Row label="Model">{p.model_id ?? "none"}</Row>
                <Row label="Compute">{titleCase(p.recommended_compute)} (recommended)</Row>
                <Row label="Estimated">
                  {p.estimated_minutes_min != null && p.estimated_minutes_max != null
                    ? `${p.estimated_minutes_min}–${p.estimated_minutes_max} minutes`
                    : "unknown"}
                  <span className="block text-xs text-fg-muted">{p.estimate_note}</span>
                </Row>
              </dl>
            )}
            {p.blockers.length > 0 && (
              <div className="mt-4">
                <Alert tone="warning" title="Cannot start yet">
                  <ul className="list-disc pl-5">
                    {p.blockers.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </Alert>
              </div>
            )}
            {start.isError && (
              <div className="mt-4">
                <Alert tone="danger">{describeError(start.error)}</Alert>
              </div>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose} disabled={start.isPending}>
                Cancel
              </Button>
              <Button
                disabled={!p.learnable || start.isPending}
                onClick={() => {
                  start.mutate(skillId, { onSuccess: onClose });
                }}
              >
                {start.isPending ? "Starting…" : "Start learning"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TrainDialog({ skillId, onClose }: { skillId: string; onClose: () => void }) {
  const [duration, setDuration] = useState(15);
  const [focus, setFocus] = useState("");
  const [target, setTarget] = useState("");
  const request: TrainRequest = {
    duration_seconds: duration * 60,
    all_areas: focus === "all",
    specialization: focus && focus !== "all" ? focus : null,
    target_level: target ? Number(target) : null,
  };
  const preview = useTrainPreview(skillId, request);
  const start = useStartTrain();
  const runs = useTrainingRuns(skillId);
  const p: TrainPreview | undefined = preview.data;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="train-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
    >
      <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-card border border-border bg-bg-elevated p-6 shadow-card">
        {preview.isPending && <Spinner />}
        {preview.isError && <Alert tone="danger">{describeError(preview.error)}</Alert>}
        {p && (
          <>
            <h2 id="train-title" className="text-lg font-bold">
              {p.icon} Train {p.name}
            </h2>
            <p className="mt-2 text-sm">{p.what_happens}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label className="text-sm">
                <span className="block text-fg-muted">Minutes</span>
                <input
                  type="number"
                  min={1}
                  max={480}
                  value={duration}
                  onChange={(e) => {
                    setDuration(Math.max(1, Number(e.target.value) || 1));
                  }}
                  className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1"
                />
              </label>
              <label className="text-sm">
                <span className="block text-fg-muted">Focus</span>
                <select
                  value={focus}
                  onChange={(e) => {
                    setFocus(e.target.value);
                  }}
                  className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1"
                >
                  <option value="">Weakest area</option>
                  <option value="all">Every area</option>
                  {p.areas.map((a) => (
                    <option key={a} value={a}>
                      {titleCase(a)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="block text-fg-muted">Stop at level</span>
                <input
                  type="number"
                  min={1}
                  max={100}
                  placeholder="optional"
                  value={target}
                  onChange={(e) => {
                    setTarget(e.target.value);
                  }}
                  className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1"
                />
              </label>
            </div>
            <dl className="mt-4 space-y-1 text-sm">
              <Row label="Current level">{p.current_level}</Row>
              <Row label="Focus">{p.focus_note}</Row>
              <Row label="Budget">
                {p.budget_minutes} minutes
                <span className="block text-xs text-fg-muted">{p.budget_note}</span>
              </Row>
              <Row label="Practice">
                {p.search_tasks} tasks to search with, {p.check_tasks} to confirm with
                <span className="block text-xs text-fg-muted">
                  The benchmark that sets the level is a separate set training never sees.
                </span>
              </Row>
              <Row label="Estimated">
                {p.estimated_rounds_min != null && p.estimated_rounds_max != null
                  ? `${p.estimated_rounds_min}\u2013${p.estimated_rounds_max} rounds`
                  : "unknown"}
                <span className="block text-xs text-fg-muted">{p.estimate_note}</span>
              </Row>
              <Row label="Model">{p.model_id ?? "none"}</Row>
              {p.resume_rounds > 0 && (
                <Row label="Continuing">from an earlier run of {p.resume_rounds} rounds</Row>
              )}
            </dl>
            {p.blockers.length > 0 && (
              <div className="mt-4">
                <Alert tone="warning" title="Cannot start yet">
                  <ul className="list-disc pl-5">
                    {p.blockers.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </Alert>
              </div>
            )}
            {start.isError && (
              <div className="mt-4">
                <Alert tone="danger">{describeError(start.error)}</Alert>
              </div>
            )}
            {runs.data && runs.data.length > 0 && (
              <div className="mt-5">
                <h3 className="text-sm font-semibold">Earlier runs</h3>
                <ul className="mt-2 space-y-2 text-xs text-fg-muted">
                  {runs.data.slice(0, 3).map((r) => (
                    <li key={r.id}>
                      {new Date(r.started_at).toLocaleDateString()} \u00b7 {r.rounds_completed}{" "}
                      rounds \u00b7 {r.summary}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose} disabled={start.isPending}>
                Cancel
              </Button>
              <Button
                disabled={!p.trainable || start.isPending}
                onClick={() => {
                  start.mutate({ skill_id: skillId, request }, { onSuccess: onClose });
                }}
              >
                {start.isPending ? "Starting\u2026" : "Start training"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TrainingRunsList({ runs }: { runs: TrainingRunRead[] }) {
  return (
    <ul className="mt-3 space-y-2 text-sm">
      {runs.map((run) => (
        <li key={run.id} className="rounded-xl border border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {new Date(run.started_at).toLocaleString()} \u00b7 {run.rounds_completed} rounds
            </span>
            <StatusPill tone={run.applied ? "success" : "muted"}>
              {run.applied ? "kept" : run.status.replace("_", " ")}
            </StatusPill>
          </div>
          <p className="mt-1 text-fg-muted">{run.summary}</p>
          {run.rounds.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-fg-muted">
              {run.rounds.map((r) => (
                <li key={r.index}>
                  {r.accepted ? "\u2713" : "\u00b7"} {r.change} ({Math.round(r.search_score * 100)}
                  %)
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

function EvaluationsDialog({ skillId, onClose }: { skillId: string; onClose: () => void }) {
  const evaluations = useEvaluations(skillId);
  const runs = useTrainingRuns(skillId);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="evals-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
    >
      <div className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-card border border-border bg-bg-elevated p-6 shadow-card">
        <h2 id="evals-title" className="text-lg font-bold">
          {titleCase(skillId)} benchmark runs
        </h2>
        {evaluations.isPending && <Spinner />}
        {evaluations.data?.map((e) => (
          <EvaluationDetail key={e.id} evaluation={e} />
        ))}
        {runs.data && runs.data.length > 0 && (
          <section className="mt-6">
            <h3 className="text-sm font-semibold">Training runs</h3>
            <p className="text-xs text-fg-muted">
              Training searches for better instructions. A level shown above only ever came from a
              benchmark run.
            </p>
            <TrainingRunsList runs={runs.data} />
          </section>
        )}
        <div className="mt-4 flex justify-end">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function EvaluationDetail({ evaluation: e }: { evaluation: EvaluationRead }) {
  const [open, setOpen] = useState(false);
  const tasks = e.task_results as Array<{
    task_id: string;
    area: string;
    score: number;
    passed: boolean;
    answer: string;
    details: string[];
  }>;
  return (
    <div className="mt-4 rounded-xl border border-border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>
          {new Date(e.evaluated_at).toLocaleString()} · level {e.level_before} → {e.level_after} ·{" "}
          {Math.round(e.score * 100)}% · {e.model_id} · package v{e.package_version}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(!open);
          }}
        >
          {open ? "Hide tasks" : `Show ${tasks.length} tasks`}
        </Button>
      </div>
      <ul className="mt-1 flex flex-wrap gap-1">
        {Object.entries(e.area_scores).map(([area, score]) => (
          <li key={area} className="rounded-md bg-bg-muted px-2 py-0.5 text-xs text-fg-muted">
            {titleCase(area)} {Math.round(score * 100)}%
          </li>
        ))}
      </ul>
      {open && (
        <ul className="mt-3 space-y-2">
          {tasks.map((t) => (
            <li key={t.task_id} className="rounded-lg bg-bg p-2">
              <div className="flex items-center gap-2 text-xs">
                <StatusPill tone={t.passed ? "success" : "danger"}>
                  {t.passed ? "pass" : `${Math.round(t.score * 100)}%`}
                </StatusPill>
                <span className="font-mono">{t.task_id}</span>
                <span className="text-fg-muted">{titleCase(t.area)}</span>
              </div>
              <pre className="mt-1 font-sans text-xs whitespace-pre-wrap text-fg-muted">
                {t.answer || "(empty answer)"}
              </pre>
              <ul className="mt-1 text-[11px] text-fg-muted">
                {t.details.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HistoryCard() {
  const history = useSkillHistory();
  return (
    <Card title="History">
      {history.isPending && <Spinner />}
      {history.data && history.data.length === 0 && (
        <p className="text-sm text-fg-muted">
          No benchmark runs yet. Every level change will appear here with the model that produced
          it.
        </p>
      )}
      {history.data && history.data.length > 0 && (
        <ul className="divide-y divide-border text-sm">
          {history.data.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="w-36 text-fg-muted">
                {new Date(e.evaluated_at).toLocaleString()}
              </span>
              <span className="font-medium">{titleCase(e.skill_id)}</span>
              <span className="tabular-nums">
                {e.level_before} → {e.level_after}
              </span>
              <span className="text-fg-muted">
                {Math.round(e.score * 100)}% · {e.model_id}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function DegreesCard({ degrees }: { degrees: DegreeStatus[] }) {
  return (
    <Card title="Degrees">
      <ul className="space-y-2 text-sm">
        {degrees.map((d) => (
          <li key={d.id} className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden>
              {d.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{d.name}</span>
                {d.earned ? (
                  <LevelBadge level={d.level} size="sm" />
                ) : (
                  <StatusPill tone="muted">not earned</StatusPill>
                )}
              </div>
              <div className="text-xs text-fg-muted">{d.note}</div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function AchievementsCard({ achievements }: { achievements: AchievementStatus[] }) {
  return (
    <Card title="Achievements">
      <ul className="space-y-2 text-sm">
        {achievements.map((a) => (
          <li
            key={a.id}
            className={a.earned ? "flex items-start gap-3" : "flex items-start gap-3 opacity-70"}
          >
            <span className="text-2xl" aria-hidden>
              {a.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{a.name}</span>
                <StatusPill tone={a.earned ? "success" : "muted"}>
                  {a.earned ? "earned" : a.progress}
                </StatusPill>
              </div>
              <div className="text-xs text-fg-muted">{a.requirement}</div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
