export function toReactReportUrl(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  if (raw.startsWith("/react/execution/results/")) {
    return raw;
  }
  if (raw.startsWith("/execution/results/")) {
    return `/react${raw}`;
  }
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin === window.location.origin && url.pathname.startsWith("/execution/results/")) {
      return `/react${url.pathname}${url.search}`;
    }
  } catch {
    return raw;
  }
  return raw;
}

