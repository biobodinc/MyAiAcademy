/** Presentation helpers shared by desktop and mobile. */

const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

export function formatBytes(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < UNITS.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? Math.round(size) : size.toFixed(digits)} ${UNITS[unit]}`;
}

export function formatPercent(fraction: number): string {
  return `${Math.round(Math.min(1, Math.max(0, fraction)) * 100)}%`;
}

export function titleCase(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export const TIER_LABELS: Record<string, string> = {
  entry: "Entry",
  basic: "Basic",
  capable: "Capable",
  powerful: "Powerful",
  workstation: "Workstation",
};

export const BAND_LABELS: Record<string, string> = {
  unlearned: "Not learned",
  beginner: "Beginner",
  developing: "Developing",
  capable: "Capable",
  advanced: "Advanced",
  expert: "Expert",
};
