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

export async function getJson<T>(url: string): Promise<T> {
  const response = await authFetch(url, { cache: "no-store" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = String(payload?.detail || payload?.message || response.statusText);
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
      detail = String(data?.detail || data?.message || response.statusText);
    } catch {
      // Keep response status text.
    }
    throw new Error(`请求失败(${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}
