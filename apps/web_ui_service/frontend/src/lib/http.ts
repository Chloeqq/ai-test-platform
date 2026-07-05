import { getStoredToken } from "./auth";

function shouldAttachToken(url: string): boolean {
  return url.startsWith("/") || url.startsWith(window.location.origin);
}

export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const token = getStoredToken();
  if (token && shouldAttachToken(url) && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, {
    ...init,
    headers,
  });
}

function readErrorDetail(payload: unknown, statusText: string): string {
  function formatLooseValue(value: unknown): string {
    if (typeof value === "string") {
      const text = value.trim();
      if (!text) {
        return "";
      }
      if ((text.startsWith("{") && text.endsWith("}")) || (text.startsWith("[") && text.endsWith("]"))) {
        try {
          return formatLooseValue(JSON.parse(text));
        } catch {
          return text;
        }
      }
      return text;
    }
    if (Array.isArray(value)) {
      return value.map((item) => formatLooseValue(item)).filter(Boolean).join("；");
    }
    if (value && typeof value === "object") {
      const row = value as Record<string, unknown>;
      const code = String(row.code || row.reason_code || "").trim();
      const message = String(row.message || row.reason || row.detail || "").trim();
      const extras: string[] = [];
      const nestedError = formatLooseValue(row.upstream_error);
      if (nestedError) {
        extras.push(`上游: ${nestedError}`);
      }
      const nestedDetail = formatLooseValue(row.detail);
      if (nestedDetail && nestedDetail !== message) {
        extras.push(`详情: ${nestedDetail}`);
      }
      if (Array.isArray(row.errors) && row.errors.length) {
        const errors = row.errors.map((item) => formatLooseValue(item)).filter(Boolean);
        if (errors.length) {
          extras.push(`原因: ${errors.join("；")}`);
        }
      }
      if (Array.isArray(row.warnings) && row.warnings.length) {
        const warnings = row.warnings.map((item) => formatLooseValue(item)).filter(Boolean);
        if (warnings.length) {
          extras.push(`提示: ${warnings.join("；")}`);
        }
      }
      if (code && message) {
        return [`[${code}] ${message}`, ...extras].join("；");
      }
      if (message) {
        return [message, ...extras].join("；");
      }
      try {
        const jsonText = JSON.stringify(row);
        return extras.length ? [jsonText, ...extras].join("；") : jsonText;
      } catch {
        return extras.join("；");
      }
    }
    return String(value || "").trim();
  }

  if (!payload || typeof payload !== "object") {
    return statusText;
  }
  const record = payload as Record<string, unknown>;
  const detail = record.detail ?? record.message ?? statusText;
  if (typeof detail === "string") {
    return detail || statusText;
  }
  if (Array.isArray(detail)) {
    const rows = detail
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }
        if (item && typeof item === "object") {
          const row = item as Record<string, unknown>;
          const msg = String(row.msg || row.message || "").trim();
          if (msg) {
            return msg;
          }
          try {
            return JSON.stringify(row);
          } catch {
            return "";
          }
        }
        return "";
      })
      .filter(Boolean);
    return rows.length ? rows.join("；") : statusText;
  }
  if (detail && typeof detail === "object") {
    const row = detail as Record<string, unknown>;
    const code = String(row.code || "").trim();
    const message = String(row.message || row.reason || row.detail || "").trim();
    const extras: string[] = [];
    const suggestedCode = String(row.suggested_code || "").trim();
    if (suggestedCode) {
      extras.push(`推荐编码: ${suggestedCode}`);
    }
    if (Array.isArray(row.errors) && row.errors.length) {
      const errors = row.errors.map((item) => formatLooseValue(item)).filter(Boolean);
      if (errors.length) {
        extras.push(`原因: ${errors.join("；")}`);
      }
    }
    const upstreamError = formatLooseValue(row.upstream_error);
    if (upstreamError) {
      extras.push(`上游: ${upstreamError}`);
    }
    if (code && message) {
      return [`[${code}] ${message}`, ...extras].join("；");
    }
    if (message) {
      return [message, ...extras].join("；");
    }
    try {
      const jsonText = JSON.stringify(row);
      return extras.length ? [jsonText, ...extras].join("；") : jsonText;
    } catch {
      return statusText;
    }
  }
  return statusText;
}

export async function getJson<T>(url: string): Promise<T> {
  const response = await authFetch(url, { cache: "no-store" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = readErrorDetail(payload, response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}

export async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await authFetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload ?? {}),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = readErrorDetail(data, response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}

export async function postFormData<T>(url: string, payload: FormData): Promise<T> {
  const response = await authFetch(url, {
    method: "POST",
    body: payload,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = readErrorDetail(data, response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}

export async function putJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await authFetch(url, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload ?? {}),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = readErrorDetail(data, response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}

export async function deleteJson<T>(url: string): Promise<T> {
  const response = await authFetch(url, {
    method: "DELETE",
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = readErrorDetail(data, response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}
