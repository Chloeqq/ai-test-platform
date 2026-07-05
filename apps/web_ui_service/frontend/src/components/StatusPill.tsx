interface StatusPillProps {
  value: unknown;
  labels?: Record<string, string>;
  prefix?: string;
  fallback?: string;
}

function normalizeStatus(value: unknown): string {
  return String(value || "").trim().toLowerCase();
}

function statusClass(prefix: string, value: unknown): string {
  const normalized = normalizeStatus(value).replace(/[^a-z0-9_-]+/g, "-") || "unknown";
  return `status-pill ${prefix}-${normalized}`;
}

export function statusLabel(value: unknown, labels: Record<string, string> = {}, fallback = "-"): string {
  const normalized = normalizeStatus(value);
  if (!normalized) {
    return fallback;
  }
  return labels[normalized] || normalized;
}

export function StatusPill({ value, labels = {}, prefix = "status", fallback = "-" }: StatusPillProps) {
  return <span className={statusClass(prefix, value)}>{statusLabel(value, labels, fallback)}</span>;
}
