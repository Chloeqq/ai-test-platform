const DEFAULT_TIME_ZONE = "Asia/Shanghai";

const ISO_WITHOUT_TIME_ZONE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/u;

function normalizeBackendDateTime(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  const normalized = raw.replace(" ", "T");
  if (ISO_WITHOUT_TIME_ZONE.test(normalized)) {
    return `${normalized}Z`;
  }
  return normalized;
}

export function parseBackendDateTime(value: unknown): Date | null {
  const normalized = normalizeBackendDateTime(value);
  if (!normalized) {
    return null;
  }
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateTime(value: unknown, options?: { timeZone?: string }): string {
  const parsed = parseBackendDateTime(value);
  if (!parsed) {
    const raw = String(value || "").trim();
    return raw || "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: options?.timeZone || DEFAULT_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
}
