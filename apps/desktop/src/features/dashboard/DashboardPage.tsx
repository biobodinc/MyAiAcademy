import { formatBytes, TIER_LABELS } from "@myai/api-client";
import { Link } from "react-router";

import {
  Alert,
  Button,
  Card,
  LevelBadge,
  PhaseTag,
  Spinner,
  StatusPill,
} from "../../components/ui";
import {
  describeError,
  useHardware,
  useProfile,
  useSkills,
  useStatus,
  useStorage,
} from "../../lib/api";
import { primaryGpu } from "../hardware/model";

const quickActions = [
  { to: "/console", label: "Console", hint: "Run /help, /status, /hardware", ready: true },
  { to: "/console", label: "Chat", hint: "Local model needed", ready: false, phase: 2 },
  { to: "/skills", label: "Learn", hint: "Skill packages", ready: false, phase: 3 },
  { to: "/skills", label: "Train", hint: "Training jobs", ready: false, phase: 4 },
  { to: "/skills", label: "Skills", hint: "Tree and levels", ready: true },
  { to: "/storage", label: "Storage", hint: "Where MyAI lives", ready: true },
];

export function DashboardPage() {
  const profile = useProfile();
  const skills = useSkills();
  const status = useStatus();
  const hardware = useHardware();
  const storage = useStorage();

  if (profile.isPending || skills.isPending) return <Spinner />;
  if (profile.isError) return <Alert tone="danger">{describeError(profile.error)}</Alert>;
  const p = profile.data;
  const gpu = hardware.data ? primaryGpu(hardware.data) : null;

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-6">
          <LevelBadge level={skills.data?.overall_level ?? 0} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold tracking-wide text-fg-muted uppercase">
              Your AI
            </div>
            <h1 className="text-3xl font-bold tracking-tight">{p?.name ?? "Unnamed"}</h1>
            <p className="text-sm text-fg-muted">{p?.personality || "No personality set yet."}</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusPill tone="success">Ready · running locally</StatusPill>
            <StatusPill tone="warning">Model not set up (Phase 2)</StatusPill>
          </div>
        </div>
      </Card>

      <div className="grid gap-5 md:grid-cols-[2fr_1fr]">
        <Card
          title="Skills"
          action={
            <Link to="/skills" className="text-sm text-accent">
              View tree →
            </Link>
          }
        >
          {skills.data && skills.data.skills.every((s) => !s.learned) ? (
            <p className="text-sm text-fg-muted">
              No skills learned yet. Your AI's first skill arrives with <code>/learn</code> in Phase
              3; until then the catalog shows what it will be able to learn.
            </p>
          ) : null}
          <ul className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
            {skills.data?.skills.map((s) => (
              <li
                key={s.id}
                className="flex items-center gap-2 rounded-xl bg-bg-muted px-3 py-2 text-sm"
              >
                <span aria-hidden>{s.icon}</span>
                <span className="flex-1 truncate">{s.name}</span>
                <LevelBadge level={s.level} size="sm" />
              </li>
            ))}
          </ul>
        </Card>

        <Card title="System">
          <dl className="space-y-2 text-sm">
            <Row
              label="Internet"
              value={
                status.data?.internet === "available"
                  ? "Online"
                  : status.data?.internet === "unavailable"
                    ? "Offline"
                    : "…"
              }
            />
            <Row label="GPU" value={gpu ? gpu.name : hardware.isPending ? "…" : "None"} />
            <Row label="VRAM" value={gpu ? formatBytes(gpu.vram_total_bytes, 0) : "—"} />
            <Row label="RAM" value={formatBytes(hardware.data?.memory.total_bytes, 0)} />
            <Row
              label="Tier"
              value={hardware.data ? (TIER_LABELS[hardware.data.tier.tier] ?? "") : "…"}
            />
            <Row
              label="Storage"
              value={
                storage.data?.configured
                  ? formatBytes(storage.data.total_bytes_used) + " used"
                  : "Not set"
              }
            />
            <Row label="Cloud uploads" value={String(status.data?.cloud_uploads ?? 0)} />
          </dl>
        </Card>
      </div>

      <Card title="Quick actions">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {quickActions.map((a) => (
            <Link
              key={a.label}
              to={a.to}
              aria-disabled={!a.ready}
              className={
                a.ready
                  ? "rounded-xl border border-border bg-bg p-4 transition hover:border-accent"
                  : "rounded-xl border border-dashed border-border bg-bg p-4 opacity-70"
              }
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">{a.label}</span>
                {!a.ready && a.phase && <PhaseTag phase={a.phase} />}
              </div>
              <div className="text-xs text-fg-muted">{a.hint}</div>
            </Link>
          ))}
        </div>
      </Card>

      {!storage.data?.configured && (
        <Alert tone="warning" title="Storage location not set">
          Choose where models and training data will live before learning skills.{" "}
          <Link to="/storage">
            <Button size="sm" variant="secondary" className="ml-2">
              Set up storage
            </Button>
          </Link>
        </Alert>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="truncate text-right font-medium">{value}</dd>
    </div>
  );
}
