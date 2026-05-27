(function () {
  const shell = document.getElementById("login-shell");
  if (!shell) return;

  const els = {
    form: document.getElementById("login-form"),
    username: document.getElementById("login-username"),
    password: document.getElementById("login-password"),
    remember: document.getElementById("login-remember"),
    submit: document.getElementById("login-submit"),
    status: document.getElementById("login-status"),
  };

  const auth = window.platformAuth || null;

  function safeNextPath() {
    const value = String(shell.dataset.nextPath || "/ai-generation").trim();
    if (!value.startsWith("/") || value.startsWith("//")) {
      return "/ai-generation";
    }
    return value;
  }

  function setStatus(message, state) {
    if (!els.status) return;
    els.status.textContent = String(message || "");
    els.status.dataset.state = String(state || "idle");
  }

  async function redirectIfAuthenticated() {
    if (!auth || typeof auth.refreshCurrentUser !== "function") return;
    const user = await auth.refreshCurrentUser();
    if (user && user.username) {
      setStatus(`已识别当前登录用户 ${user.username}，正在跳转。`, "success");
      window.location.replace(safeNextPath());
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const username = String(els.username?.value || "").trim();
    const password = String(els.password?.value || "");
    if (!username || !password) {
      setStatus("请输入用户名和密码。", "error");
      return;
    }

    els.submit.disabled = true;
    setStatus("登录中，请稍候...", "loading");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || response.statusText || "登录失败");
      }
      if (!payload?.access_token || !auth || typeof auth.setToken !== "function") {
        throw new Error("登录成功，但未拿到有效 token");
      }
      auth.setToken(payload.access_token, els.remember?.checked ? "local" : "session");
      if (typeof auth.refreshCurrentUser === "function") {
        await auth.refreshCurrentUser();
      }
      setStatus(`登录成功，正在返回 ${safeNextPath()} ...`, "success");
      window.location.replace(safeNextPath());
    } catch (error) {
      console.error(error);
      setStatus(error?.message || "登录失败，请稍后重试。", "error");
      els.submit.disabled = false;
      if (els.password) {
        els.password.select();
      }
    }
  }

  els.form?.addEventListener("submit", handleSubmit);
  redirectIfAuthenticated().catch((error) => {
    console.error(error);
  });
})();
