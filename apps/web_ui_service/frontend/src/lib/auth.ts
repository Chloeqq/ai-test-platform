const STORAGE_KEYS = [
  "ai_test_platform.access_token",
  "access_token",
  "auth_token",
  "token",
  "jwt",
];

type PersistScope = "local" | "session";

function readTokenFrom(storage: Storage | null): string {
  if (!storage) {
    return "";
  }
  for (const key of STORAGE_KEYS) {
    try {
      const value = String(storage.getItem(key) || "").trim();
      if (value) {
        return value;
      }
    } catch {
      return "";
    }
  }
  return "";
}

export function getStoredToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return readTokenFrom(window.localStorage) || readTokenFrom(window.sessionStorage);
}

function eachStorage(callback: (storage: Storage) => void): void {
  if (typeof window === "undefined") {
    return;
  }
  [window.localStorage, window.sessionStorage].forEach((storage) => {
    try {
      callback(storage);
    } catch {
      // Ignore storage access errors.
    }
  });
}

export function clearStoredToken(): void {
  eachStorage((storage) => {
    STORAGE_KEYS.forEach((key) => {
      storage.removeItem(key);
    });
  });
}

export function setStoredToken(token: string, scope: PersistScope = "local"): void {
  const normalized = String(token || "").trim();
  clearStoredToken();
  if (!normalized || typeof window === "undefined") {
    return;
  }
  const target = scope === "session" ? window.sessionStorage : window.localStorage;
  target.setItem(STORAGE_KEYS[0], normalized);
}
