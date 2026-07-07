export const DEFAULT_PROJECT_CODE = "mall";

export function normalizeProjectCode(value: unknown): string {
  return String(value || "").trim() || DEFAULT_PROJECT_CODE;
}

export function projectOptions(codes: unknown): string[] {
  const rawCodes = Array.isArray(codes) ? codes : [];
  const seen = new Set<string>();
  const items: string[] = [];
  [DEFAULT_PROJECT_CODE, ...rawCodes].forEach((value) => {
    const code = String(value || "").trim();
    if (!code || code === "default" || seen.has(code)) {
      return;
    }
    seen.add(code);
    items.push(code);
  });
  return items;
}
