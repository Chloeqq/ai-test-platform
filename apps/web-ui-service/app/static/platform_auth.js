(function () {
  const STORAGE_KEYS = ["ai_test_platform.access_token", "access_token", "auth_token", "token", "jwt"];
  const shell = {
    box: document.getElementById("platform-user-box"),
    avatar: document.getElementById("platform-user-avatar"),
    name: document.getElementById("platform-user-name"),
    authLink: document.getElementById("platform-auth-link"),
  };

  const state = {
    user: null,
    authState: "unknown",
  };

  function firstDefined(values) {
    for (const value of values) {
      if (value !== null && value !== undefined) {
        return value;
      }
    }
    return null;
  }

  function readTokenFrom(storage) {
    if (!storage) return "";
    for (const key of STORAGE_KEYS) {
      try {
        const value = String(storage.getItem(key) || "").trim();
        if (value) return value;
      } catch (_error) {
        return "";
      }
    }
    return "";
  }

  function getStoredToken() {
    return readTokenFrom(window.localStorage) || readTokenFrom(window.sessionStorage) || "";
  }

  function buildInitial(name, fallback) {
    const value = String(name || "").trim();
    if (!value) return String(fallback || "?").slice(0, 1);
    return value.slice(0, 1).toUpperCase();
  }

  function setUserBox(name, initial, authState) {
    if (!shell.box || !shell.avatar || !shell.name) return;
    const resolvedName = String(name || shell.box.dataset.defaultName || "访客").trim() || "访客";
    const resolvedInitial = buildInitial(initial || resolvedName, shell.box.dataset.defaultInitial || "访");
    shell.box.dataset.authState = String(authState || "unknown");
    shell.avatar.textContent = resolvedInitial;
    shell.name.textContent = resolvedName;
  }

  function updateAuthLink(authState) {
    if (!shell.authLink) return;
    const stateValue = String(authState || "anonymous");
    shell.authLink.dataset.authState = stateValue;
    if (stateValue === "authenticated" || stateValue === "token") {
      shell.authLink.textContent = "退出登录";
      shell.authLink.href = shell.authLink.dataset.logoutHref || window.location.pathname || "/";
    } else {
      shell.authLink.textContent = "登录";
      shell.authLink.href = shell.authLink.dataset.loginHref || "/login";
    }
  }

  function applyAnonymousState() {
    state.user = null;
    state.authState = "anonymous";
    setUserBox("访客", "访", "anonymous");
    updateAuthLink("anonymous");
    window.dispatchEvent(new CustomEvent("platform-auth-changed", { detail: { authState: state.authState, user: null } }));
  }

  function applyUser(user, authState) {
    const username = String(firstDefined([user?.username, user?.name]) || "").trim();
    if (!username) {
      applyAnonymousState();
      return;
    }
    state.user = user;
    state.authState = String(authState || "authenticated");
    setUserBox(username, buildInitial(username, "访"), state.authState);
    updateAuthLink(state.authState);
    window.dispatchEvent(new CustomEvent("platform-auth-changed", { detail: { authState: state.authState, user: state.user } }));
  }

  function shouldAttachToken(url) {
    const value = typeof url === "string" ? url : String(url?.url || "");
    if (!value) return true;
    return value.startsWith("/") || value.startsWith(window.location.origin);
  }

  async function authFetch(url, options) {
    const nextOptions = options && typeof options === "object" ? { ...options } : {};
    const headers = new Headers(nextOptions.headers || {});
    const token = getStoredToken();
    if (token && shouldAttachToken(url) && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    nextOptions.headers = headers;
    return fetch(url, nextOptions);
  }

  async function refreshCurrentUser() {
    const token = getStoredToken();
    if (!token) {
      applyAnonymousState();
      return null;
    }
    try {
      const response = await authFetch("/api/auth/me", { cache: "no-store" });
      if (!response.ok) {
        applyAnonymousState();
        return null;
      }
      const payload = await response.json();
      applyUser(payload, "token");
      return payload;
    } catch (_error) {
      applyAnonymousState();
      return null;
    }
  }

  function setToken(token, persistTo) {
    const storage = persistTo === "session" ? window.sessionStorage : window.localStorage;
    STORAGE_KEYS.forEach((key, index) => {
      try {
        if (index === 0) {
          storage.setItem(key, String(token || ""));
        } else {
          storage.removeItem(key);
        }
      } catch (_error) {
        return;
      }
    });
  }

  function clearToken() {
    [window.localStorage, window.sessionStorage].forEach((storage) => {
      STORAGE_KEYS.forEach((key) => {
        try {
          storage.removeItem(key);
        } catch (_error) {
          return;
        }
      });
    });
    applyAnonymousState();
  }

  function bindAuthActions() {
    if (!shell.authLink) return;
    shell.authLink.addEventListener("click", function (event) {
      const stateValue = String(state.authState || "").toLowerCase();
      if (stateValue !== "authenticated" && stateValue !== "token") {
        return;
      }
      event.preventDefault();
      clearToken();
      const target = shell.authLink.dataset.loginHref || "/login";
      if (window.location.pathname === "/login") {
        window.location.reload();
        return;
      }
      window.location.href = target;
    });
  }

  window.platformAuth = {
    getToken: getStoredToken,
    getCurrentUser: function () {
      return state.user;
    },
    getAuthState: function () {
      return state.authState;
    },
    authFetch,
    refreshCurrentUser,
    setToken,
    clearToken,
  };
  window.platformAuthFetch = authFetch;

  if (shell.box) {
    setUserBox(shell.box.dataset.defaultName || "访客", shell.box.dataset.defaultInitial || "访", shell.box.dataset.authState || "server");
  }
  updateAuthLink("anonymous");
  bindAuthActions();
  refreshCurrentUser();
})();
