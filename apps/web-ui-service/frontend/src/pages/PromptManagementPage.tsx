import { Link } from "react-router-dom";

const PROMPTS = [
  {
    title: "requirement-parser.prompt.v3",
    meta: "适用：需求解析 · 模型：主模型",
    badge: "默认",
  },
  {
    title: "test-design.prompt.v2",
    meta: "适用：测试设计 · 模型：主模型",
    badge: "已发布",
  },
  {
    title: "generate.compat.v1",
    meta: "适用：兼容生成 · 模型：备用",
    badge: "备用",
  },
];

export function PromptManagementPage() {
  return (
    <main className="page shell">
      <header className="header panel unified-topbar">
        <div>
          <h1>提示词管理</h1>
          <p className="muted">高级参数页：管理 prompt 版本、模型配置和发布回滚策略。</p>
        </div>
        <div className="header-actions unified-topbar-actions">
          <Link className="button secondary" to="/ai-generation">
            返回生成页
          </Link>
        </div>
      </header>

      <section className="panel">
        <ul className="simple-list">
          {PROMPTS.map((item) => (
            <li key={item.title} className="simple-list-item">
              <div>
                <strong>{item.title}</strong>
                <p className="muted">{item.meta}</p>
              </div>
              <span className="badge">{item.badge}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
