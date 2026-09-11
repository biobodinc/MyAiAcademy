import { BAND_LABELS, titleCase, type SkillStatus } from "@myai/api-client";
import { Lock } from "lucide-react";

import {
  Alert,
  Card,
  LevelBadge,
  PageHeader,
  PhaseTag,
  ProgressBar,
  Spinner,
} from "../../components/ui";
import { describeError, useSkills } from "../../lib/api";

const DOMAIN_ORDER = ["core", "creative", "technical", "knowledge"] as const;

export function SkillsPage() {
  const skills = useSkills();
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
        subtitle="Levels only change after an evaluation. Nothing here is awarded for time spent."
        action={
          <div className="flex items-center gap-2 text-sm">
            Overall <LevelBadge level={skills.data.overall_level} />
          </div>
        }
      />
      <Alert tone="info">
        Skill packages, /learn and /train arrive in Phase 3–4. The tree below shows what your AI
        will be able to learn and what each skill requires.
      </Alert>
      <div className="mt-5 space-y-6">
        {groups.map((g) => (
          <section key={g.domain}>
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-fg-muted uppercase">
              {titleCase(g.domain)}
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {g.items.map((s) => (
                <SkillCard key={s.id} skill={s} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function SkillCard({ skill }: { skill: SkillStatus }) {
  return (
    <Card className={skill.locked ? "opacity-70" : undefined}>
      <div className="flex items-start gap-3">
        <div className="text-3xl" aria-hidden>
          {skill.icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">{skill.name}</h3>
            {skill.locked && <Lock className="h-3.5 w-3.5 text-fg-muted" aria-label="Locked" />}
            <PhaseTag phase={skill.planned_phase} />
          </div>
          <p className="text-sm text-fg-muted">{skill.description}</p>
          <div className="mt-3 flex items-center gap-3">
            <LevelBadge level={skill.level} size="sm" />
            <div className="flex-1">
              <ProgressBar value={skill.level} max={100} label={`${skill.name} level`} />
            </div>
            <span className="text-xs text-fg-muted">{BAND_LABELS[skill.band] ?? skill.band}</span>
          </div>
          {skill.locked_reason && (
            <p className="mt-2 text-xs text-warning">{skill.locked_reason}</p>
          )}
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
