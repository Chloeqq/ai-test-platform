import { type FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getCurrentUser, login } from "../api/auth";
import { clearStoredToken, getStoredToken, setStoredToken } from "../lib/auth";

function safeNextPath(value: string): string {
  const normalized = String(value || "").trim();
  if (!normalized.startsWith("/") || normalized.startsWith("//")) {
    return "/ai-generation";
  }
  return normalized;
}

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [remember, setRemember] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusText, setStatusText] = useState<string>("请输入账号密码。");
  const forceLogin = String(searchParams.get("force") || "").trim() === "1";

  const nextPath = safeNextPath(searchParams.get("next") || "/ai-generation");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (forceLogin) {
        clearStoredToken();
        setStatusText("已进入重新登录模式，请输入账号密码。");
        return;
      }
      const token = getStoredToken();
      if (!token) {
        return;
      }
      try {
        const user = await getCurrentUser();
        if (cancelled) {
          return;
        }
        if (user?.username) {
          setStatusText(`已识别当前登录用户 ${user.username}，正在跳转。`);
          window.location.replace(nextPath);
        }
      } catch {
        clearStoredToken();
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [forceLogin, nextPath]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const inputUsername = String(username || "").trim();
    const inputPassword = String(password || "");
    if (!inputUsername || !inputPassword) {
      setStatusText("请输入用户名和密码。");
      return;
    }
    setLoading(true);
    setStatusText("登录中，请稍候...");
    try {
      const payload = await login({ username: inputUsername, password: inputPassword });
      const token = String(payload?.access_token || "").trim();
      if (!token) {
        throw new Error("登录成功，但未拿到有效 token");
      }
      setStoredToken(token, remember ? "local" : "session");
      setStatusText(`登录成功，正在返回 ${nextPath} ...`);
      window.location.replace(nextPath);
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : "登录失败，请稍后重试。");
      setLoading(false);
    }
  }

  return (
    <main className="login-shell" data-next-path={nextPath}>
      <section className="login-panel panel">
        <div className="login-brand">
          <div className="login-mark">AT</div>
          <div>
            <h1>AI Quality Assurance Platform</h1>
            <p>登录后即可将 URL 自动化、确认点审核与操作审计绑定到真实用户。</p>
          </div>
        </div>

        <div className="login-copy">
          <h2>登录平台</h2>
          <p>这一步只做确定性认证，不涉及 AI 推断。成功后会把 token 写入浏览器，并自动回到你原来的页面。</p>
        </div>

        <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            用户名
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="请输入用户名"
              disabled={loading}
            />
          </label>
          <label>
            密码
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入密码"
              disabled={loading}
            />
          </label>
          <label className="login-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
              disabled={loading}
            />
            <span>记住登录状态</span>
          </label>
          <button type="submit" className="login-submit" disabled={loading}>
            登录并返回
          </button>
        </form>

        <div className="login-status" data-state={statusText.includes("成功") ? "success" : statusText.includes("失败") ? "error" : "idle"}>
          {statusText}
        </div>
        <p className="login-note">说明：若页面上方已显示真实用户名，你可以直接返回工作台，无需重复登录。</p>
      </section>
    </main>
  );
}
