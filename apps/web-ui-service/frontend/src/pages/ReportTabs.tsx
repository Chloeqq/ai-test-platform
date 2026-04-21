import { NavLink } from "react-router-dom";

const TABS: Array<{ to: string; label: string }> = [
  { to: "/execution/results", label: "总览" },
  { to: "/execution/results/failures", label: "失败详情" },
  { to: "/execution/results/context", label: "资产与集成" },
  { to: "/execution/results/performance", label: "性能耗时" },
  { to: "/execution/results/allure", label: "Allure" },
];

export function ReportTabs() {
  return (
    <nav className="panel tabs" aria-label="执行结果导航">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) => (isActive ? "tab active" : "tab")}
          end={tab.to === "/execution/results"}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
