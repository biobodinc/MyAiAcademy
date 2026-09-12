import { formatBytes, TIER_LABELS } from "@myai/api-client";
import { Link } from "react-router";

import {
  Alert,
  Button,
  Card,
  LevelBadge,
  PhaseTag,
  ProgressBar,
  Spinner,
  StatusPill,
} from "../../components/ui";
import {
  describeError,
  useHardware,
  useMetrics,
  useProfile,
  useSkills,
  useStatus,
  useStorage,
} from "../../lib/api";
import { primaryGpu } from "../hardware/model";
import { headline } from "./model";

const quickActions = [
  { to: "/chat", label: "Chat", hint: "Talk to your AI locally", ready: true },
  { to: "/models", label: "Models", hint: "Download and activate", ready: true },
  { to: "/memory", label: "Memory", hint: "What it remembers", ready: true },
  { to: "/knowledge", label: "Knowledge", hint: "Documents it can cite", ready: true },
  { to: "/skills", label: "Learn", hint: "Skills and benchmarks", ready: true },
  { to: "/skills", label: "Train", hint: "Training jobs", ready: false, phase: 4 },
];

export function DashboardPage() {
  const profile = useProfile();
  const skills = useSkills();
  const status = useStatus();
  const hardware = useHardware();
  const storage = useStorage();
  const metrics = useMetrics();

  if (profile.isPending || skills.isPending) return <Spinner />;
  if (profile.isError) return <Alert tone="danger">{describeError(profile.error)}</Alert>;
  const p = profile.data;
  const gpu = hardware.data ? primaryGpu(hardware.data) : null;
  const current = headline(status.data);
  const m = metrics.data;

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
            <div className="text-xs text-fg-muted">Current status</div>
            <StatusPill tone={current.tone}>{current.text}</StatusPill>
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
              No skills learned yet. Open Skills or type <code>/learn conversation</code> in the
              Console to learn the first one: its benchmark sets the level.
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
          <dl className="space-y-3 text-sm">
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
            <Meter
              label="CPU"
              percent={m?.cpu_percent ?? null}
              detail={
                hardware.data?.cpu.physical_cores ? `${hardware.data.cpu.physical_cores} cores` : ""
              }
            />
            <Meter
              label="RAM"
              percent={m?.memory_percent ?? null}
              detail={
                m?.memory_used_bytes != null
                  ? `${formatBytes(m.memory_used_bytes, 0)} of ${formatBytes(m.memory.total_bytes, 0)}`
                  : formatBytes(hardware.data?.memory.total_bytes, 0)
              }
            />
            <Meter
              label="GPU"
              percent={m?.gpu?.utilization_percent ?? null}
              detail={
                m?.gpu
                  ? m.gpu.utilization_percent == null
                    ? `${m.gpu.name} · no live counters`
                    : `${m.gpu.name}${m.gpu.temperature_c != null ? ` · ${Math.round(m.gpu.temperature_c)}°C` : ""}`
                  : gpu
                    ? gpu.name
                    : hardware.isPending
                      ? "…"
                      : "None detected"
              }
            />
            {m?.battery?.percent != null && (
              <Row
                label="Battery"
                value={`${Math.round(m.battery.percent)}% · ${m.battery.plugged_in ? "plugged in" : "on battery"}`}
              />
            )}
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
          <p className="mt-3 text-[10px] text-fg-muted">
            Whole-machine figures, refreshed every few seconds.
          </p>
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

      {storage.data?.configured && status.data?.ai === "not_configured" && (
        <Alert tone="info" title="Your AI cannot chat yet">
          Download a local model to start talking.{" "}
          <Link to="/models">
            <Button size="sm" variant="secondary" className="ml-2">
              Choose a model
            </Button>
          </Link>
        </Alert>
      )}
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

function Meter({
  label,
  percent,
  detail,
}: {
  label: string;
  percent: number | null;
  detail: string;
}) {
  return (
    <div>
      <div className="flex justify-between gap-3">
        <dt className="text-fg-muted">{label}</dt>
        <dd className="truncate text-right font-medium">
          {percent == null ? detail || "—" : `${Math.round(percent)}%`}
        </dd>
      </div>
      {percent != null && (
        <>
          <div className="mt-1">
            <ProgressBar
              value={percent}
              label={`${label} utilisation`}
              tone={percent > 90 ? "danger" : percent > 70 ? "warning" : "accent"}
            />
          </div>
          {detail && <div className="mt-0.5 text-[10px] text-fg-muted">{detail}</div>}
        </>
      )}
    </div>
  );
}
