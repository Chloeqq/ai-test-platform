(function () {
  const STORAGE_KEY = "platform_access_token";
  const state = {
    token: "",
    currentUser: null,
    authState: "anonymous",
  };

  function safeStorageGet() {
    try {
      return String(window.localStorage.getItem(STORAGE_KEY) || "");
    } catch (_error) {
      return "";
    }
  }

  function safeStorageSet(token) {
    try {
      if (!token) window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, token);
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function parseJwtPayload(token) {
    if (!token || !token.includes(".")) return null;
    try {
      const payload = token.split(".")[1];
      const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
      const decoded = window.atob(normalized);
      const obj = JSON.parse(decoded);
      return obj && typeof obj === "object" ? obj : null;
    } catch (_error) {
      return null;
    }
  }

  function getFallbackUser() {
    const payload = parseJwtPayload(state.token);
    if (!payload) return null;
    const username = String(payload.username || payload.sub || "").trim();
    if (!username) return null;
    return {
      id: payload.sub || "",
      username: username,
      role: payload.role || "",
      name: username,
    };
  }

  function initialOf(name) {
    const text = String(name || "").trim();
    if (!text) return "访";
    return text.slice(0, 1).toUpperCase();
  }

  function applyAuthUi() {
    const authLink = document.getElementById("platform-auth-link");
    const userBox = document.getElementById("platform-user-box");
    const userName = document.getElementById("platform-user-name");
    const userAvatar = document.getElementById("platform-user-avatar");
    if (!authLink || !userBox || !userName || !userAvatar) return;

    if (state.authState === "authenticated" || state.authState === "token") {
      const user = state.currentUser || getFallbackUser() || {};
      const displayName = String(user.username || user.name || "当前用户").trim();
      const logoutHref = String(authLink.dataset.logoutHref || window.location.pathname || "/");
      authLink.textContent = "退出登录";
      authLink.href = logoutHref;
      authLink.dataset.authState = "authenticated";
      userBox.dataset.authState = "authenticated";
      userName.textContent = displayName;
      userAvatar.textContent = initialOf(displayName);
      return;
    }

    const defaultName = String(userBox.dataset.defaultName || "访客").trim() || "访客";
    const defaultInitial = String(userBox.dataset.defaultInitial || "访").trim() || "访";
    const loginHref = String(authLink.dataset.loginHref || "/login").trim() || "/login";
    authLink.textContent = "登录";
    authLink.href = loginHref;
    authLink.dataset.authState = "anonymous";
    userBox.dataset.authState = "anonymous";
    userName.textContent = defaultName;
    userAvatar.textContent = defaultInitial.slice(0, 1);
  }

  function emitAuthChange() {
    window.dispatchEvent(
      new CustomEvent("platform-auth-changed", {
        detail: {
          auth_state: state.authState,
          current_user: state.currentUser,
        },
      })
    );
  }

  async function authFetch(input, init) {
    const requestInit = { ...(init || {}) };
    const headers = new Headers(requestInit.headers || {});
    if (state.token) {
      headers.set("Authorization", "Bearer " + state.token);
    }
    requestInit.headers = headers;
    return window.fetch(input, requestInit);
  }

  async function refreshCurrentUser() {
    if (!state.token) {
      state.currentUser = null;
      state.authState = "anonymous";
      applyAuthUi();
      emitAuthChange();
      return null;
    }
    try {
      const response = await authFetch("/api/auth/me", { method: "GET" });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          clearToken();
        }
        state.currentUser = getFallbackUser();
        state.authState = state.currentUser ? "token" : "anonymous";
        applyAuthUi();
        emitAuthChange();
        return state.currentUser;
      }
      const payload = await response.json();
      state.currentUser = payload && typeof payload === "object" ? payload : getFallbackUser();
      state.authState = "authenticated";
      applyAuthUi();
      emitAuthChange();
      return state.currentUser;
    } catch (_error) {
      state.currentUser = getFallbackUser();
      state.authState = state.currentUser ? "token" : "anonymous";
      applyAuthUi();
      emitAuthChange();
      return state.currentUser;
    }
  }

  function setToken(token) {
    const nextToken = String(token || "").trim();
    state.token = nextToken;
    safeStorageSet(nextToken);
    state.currentUser = null;
    state.authState = nextToken ? "token" : "anonymous";
    applyAuthUi();
    emitAuthChange();
  }

  function clearToken() {
    setToken("");
  }

  function initAuthLinkBehavior() {
    const authLink = document.getElementById("platform-auth-link");
    if (!authLink) return;
    authLink.addEventListener("click", (event) => {
      const isAuthenticated = state.authState === "authenticated" || state.authState === "token";
      if (!isAuthenticated) return;
      event.preventDefault();
      clearToken();
      const next = String(authLink.dataset.logoutHref || window.location.pathname || "/");
      window.location.href = next;
    });
  }

  state.token = safeStorageGet();
  state.authState = state.token ? "token" : "anonymous";
  state.currentUser = getFallbackUser();
  applyAuthUi();
  emitAuthChange();
  initAuthLinkBehavior();
  refreshCurrentUser().catch(() => {});

  window.platformAuthFetch = authFetch;
  window.platformAuth = {
    clearToken: clearToken,
    getAuthState: function getAuthState() {
      return state.authState;
    },
    getCurrentUser: function getCurrentUser() {
      return state.currentUser;
    },
    getToken: function getToken() {
      return state.token;
    },
    refreshCurrentUser: refreshCurrentUser,
    setToken: setToken,
  };
})();
