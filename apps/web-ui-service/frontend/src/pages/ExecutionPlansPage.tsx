import { Link } from "react-router-dom";

const PLAN_ITEMS = [
  {
    title: "发布前回归计划 - 订单链路",
    meta: "范围：订单 / 退货 / 支付",
    badge: "待执行",
  },
  {
    title: "日常烟测计划 - 商品中心",
    meta: "范围：商品列表 / 新增商品",
    badge: "循环任务",
  },
  {
    title: "缺陷回归计划 - 搜索筛选",
    meta: "范围：搜索 / 筛选 / 排序",
    badge: "需确认",
  },
];

export function ExecutionPlansPage() {
  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>测试计划（React + TypeScript）</h1>
          <p className="muted">计划页仅负责计划范围、依赖和执行策略，不承载执行结果明细。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/execution/runs">
            查看执行任务
          </Link>
          <Link className="button" to="/execution/results">
            查看执行结果
          </Link>
        </div>
      </header>

      <section className="panel">
        <ul className="simple-list">
          {PLAN_ITEMS.map((item) => (
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
