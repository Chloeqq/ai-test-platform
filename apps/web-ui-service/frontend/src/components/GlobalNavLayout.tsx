import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { getCurrentUser, type AuthUser } from "../api/auth";
import { clearStoredToken, getStoredToken } from "../lib/auth";
import { Breadcrumbs } from "./Breadcrumbs";

interface NavItem {
  label: string;
  to: string;
}

interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    key: "dashboard",
    label: "仪表盘",
    items: [{ label: "总览", to: "/dashboard" }],
  },
  {
    key: "ai_generation",
    label: "AI 生成",
    items: [
      { label: "生成工作台", to: "/ai-generation" },
      { label: "生成历史", to: "/ai-generation/history" },
      { label: "提示词管理", to: "/ai-generation/prompts" },
    ],
  },
  {
    key: "assets",
    label: "测试资产",
    items: [
      { label: "用例中心", to: "/cases" },
      { label: "待审核用例", to: "/cases/review" },
      { label: "用例版本", to: "/cases/versions" },
      { label: "标签治理", to: "/cases/tags" },
      { label: "测试点资产", to: "/assets/test-points" },
      { label: "页面对象", to: "/assets/page-objects" },
      { label: "接口契约", to: "/assets/api-contracts" },
      { label: "数据模板", to: "/assets/data-templates" },
    ],
  },
  {
    key: "execution",
    label: "执行与报告",
    items: [
      { label: "执行计划", to: "/execution/plans" },
      { label: "执行记录", to: "/execution/runs" },
      { label: "结果总览", to: "/execution/results" },
      { label: "失败分析", to: "/execution/results/failures" },
      { label: "上下文", to: "/execution/results/context" },
      { label: "性能分析", to: "/execution/results/performance" },
      { label: "Allure 报告", to: "/execution/results/allure" },
    ],
  },
  {
    key: "quality",
    label: "质量治理",
    items: [
      { label: "质量仪表盘", to: "/quality/dashboard" },
      { label: "Flaky 分析", to: "/quality/flaky" },
      { label: "失败聚类", to: "/quality/failure-clusters" },
      { label: "趋势分析", to: "/quality/trends" },
      { label: "质量门禁", to: "/quality/gates" },
      { label: "质量评估中心", to: "/quality/eval" },
      { label: "缺陷看板", to: "/defects" },
    ],
  },
  {
    key: "system",
    label: "系统设置",
    items: [
      { label: "项目管理", to: "/system/projects" },
      { label: "源码管理", to: "/system/source-config" },
      { label: "任务调度", to: "/settings/scheduler" },
      { label: "环境管理", to: "/system/environments" },
      { label: "节点管理", to: "/system/nodes" },
      { label: "集成配置", to: "/system/integrations" },
      { label: "权限角色", to: "/system/roles" },
    ],
  },
];

const RECENT_PATHS_KEY = "atp_recent_paths";

function isPathActive(currentPath: string, targetPath: string): boolean {
  if (targetPath === "/dashboard") {
    return currentPath === "/dashboard";
  }
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`);
}

function resolvePathLabel(pathname: string): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (isPathActive(pathname, item.to)) {
        return item.label;
      }
    }
  }
  return pathname;
}

function buildLoginPath(nextPath: string, force = false): string {
  const query = new URLSearchParams();
  query.set("next", nextPath || "/dashboard");
  if (force) {
    query.set("force", "1");
  }
  return `/login?${query.toString()}`;
}

export function GlobalNavLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [recentPaths, setRecentPaths] = useState<string[]>([]);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [authErrorText, setAuthErrorText] = useState<string>("");

  const environment = useMemo(() => {
    const raw = String(import.meta.env.VITE_APP_ENV || import.meta.env.MODE || "dev").toLowerCase();
    if (raw === "dev" || raw === "development") {
      return "开发环境";
    }
    if (raw === "test" || raw === "testing" || raw === "qa" || raw === "staging") {
      return "测试环境";
    }
    if (raw === "prod" || raw === "production") {
      return "生产环境";
    }
    return `环境：${raw}`;
  }, []);
  const currentPathWithQuery = useMemo(
    () => `${location.pathname}${location.search}` || "/dashboard",
    [location.pathname, location.search],
  );

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const stored = window.localStorage.getItem(RECENT_PATHS_KEY);
    if (!stored) {
      return;
    }
    try {
      const parsed = JSON.parse(stored) as string[];
      setRecentPaths(Array.isArray(parsed) ? parsed.filter(Boolean).slice(0, 5) : []);
    } catch {
      setRecentPaths([]);
    }
  }, []);

  useEffect(() => {
    if (authUser) {
      setAuthChecking(false);
      return;
    }
    let cancelled = false;
    async function bootstrapAuth() {
      setAuthChecking(true);
      setAuthErrorText("");
      const token = getStoredToken();
      if (!token) {
        if (!cancelled) {
          setAuthChecking(false);
          navigate(buildLoginPath(currentPathWithQuery), { replace: true });
        }
        return;
      }
      try {
        const user = await getCurrentUser();
        if (!cancelled) {
          setAuthUser(user);
        }
      } catch (error) {
        clearStoredToken();
        if (!cancelled) {
          setAuthErrorText(error instanceof Error ? error.message : "登录状态失效，请重新登录。");
          setAuthUser(null);
          navigate(buildLoginPath(currentPathWithQuery), { replace: true });
        }
      } finally {
        if (!cancelled) {
          setAuthChecking(false);
        }
      }
    }
    void bootstrapAuth();
    return () => {
      cancelled = true;
    };
  }, [authUser, currentPathWithQuery, navigate]);

  useEffect(() => {
    if (!authUser) {
      return;
    }
    const current = location.pathname;
    if (current === "/login" || current === "/") {
      return;
    }
    setRecentPaths((prev) => {
      const next = [current, ...prev.filter((item) => item !== current)].slice(0, 5);
      window.localStorage.setItem(RECENT_PATHS_KEY, JSON.stringify(next));
      return next;
    });
  }, [location.pathname]);

  function handleLogout() {
    clearStoredToken();
    setAuthUser(null);
    setDrawerOpen(false);
    setAuthChecking(false);
    navigate(buildLoginPath("/dashboard"), { replace: true });
  }

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className={`platform-layout ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      {authErrorText ? <div className="platform-auth-error">{authErrorText}</div> : null}
      <header className="platform-topbar">
        <div className="topbar-left">
          <button type="button" className="nav-icon-button mobile-only" onClick={() => setDrawerOpen((prev) => !prev)} aria-label="打开导航">
            ☰
          </button>
          <Link className="platform-brand" to="/dashboard">
            <span className="brand-mark">ATP</span>
            <span className="brand-text">AI 质量保障平台</span>
          </Link>
          <span className="env-badge">{environment}</span>
        </div>

        <div className="topbar-right">
          {authChecking ? (
            <span className="auth-pill">登录校验中...</span>
          ) : authUser ? (
            <details className="account-menu">
              <summary className="button secondary">{authUser.username}</summary>
              <div className="account-popover">
                <Link className="account-item" to={buildLoginPath(currentPathWithQuery, true)}>
                  切换账号
                </Link>
                <button type="button" className="account-item danger" onClick={handleLogout}>
                  退出登录
                </button>
              </div>
            </details>
          ) : (
            <Link className="button secondary" to={buildLoginPath(currentPathWithQuery)}>
              登录
            </Link>
          )}
        </div>
      </header>

      <aside className={`platform-sidebar ${drawerOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <strong>导航</strong>
          <button
            type="button"
            className="nav-icon-button desktop-only"
            onClick={() => setSidebarCollapsed((prev) => !prev)}
            aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          >
            {sidebarCollapsed ? "»" : "«"}
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_GROUPS.map((group) => {
            const groupActive = group.items.some((item) => isPathActive(location.pathname, item.to));
            const isCollapsed = Boolean(collapsedGroups[group.key]);
            return (
              <section key={group.key} className={`sidebar-group ${groupActive ? "active" : ""}`}>
                <button type="button" className="group-title" onClick={() => toggleGroup(group.key)}>
                  <span>{group.label}</span>
                  <span>{isCollapsed ? "+" : "-"}</span>
                </button>
                {!isCollapsed ? (
                  <div className="group-items">
                    {group.items.map((item) => (
                      <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                        {item.label}
                      </NavLink>
                    ))}
                  </div>
                ) : null}
              </section>
            );
          })}
        </nav>

        <div className="sidebar-recent">
          <p>最近访问</p>
          <div className="group-items">
            {recentPaths.length ? (
              recentPaths.map((path) => (
                <NavLink key={path} to={path} className="nav-item">
                  {resolvePathLabel(path)}
                </NavLink>
              ))
            ) : (
              <span className="muted">暂无记录</span>
            )}
          </div>
        </div>
      </aside>

      {drawerOpen ? <button type="button" className="sidebar-backdrop" onClick={() => setDrawerOpen(false)} aria-label="关闭导航遮罩" /> : null}

      <section className="platform-content">
        {authChecking ? (
          <div className="platform-auth-screen">
            <div className="platform-auth-card">
              <h2>正在校验登录状态</h2>
              <p className="muted">请稍候，我们正在确认你的身份并恢复会话。</p>
            </div>
          </div>
        ) : (
          <>
            <Breadcrumbs />
            <Outlet />
          </>
        )}
      </section>
    </div>
  );
}
