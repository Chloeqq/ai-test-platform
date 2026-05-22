import { Link, matchPath, useLocation } from "react-router-dom";

interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface RouteCrumbContext {
  pathname: string;
  searchParams: URLSearchParams;
  params: Record<string, string | undefined>;
}

interface BreadcrumbRoute {
  path: string;
  crumbs: BreadcrumbItem[] | ((context: RouteCrumbContext) => BreadcrumbItem[]);
}

function withProject(path: string, searchParams: URLSearchParams): string {
  const project = String(searchParams.get("project") || "").trim();
  if (!project) {
    return path;
  }
  const query = new URLSearchParams();
  query.set("project", project);
  return `${path}?${query.toString()}`;
}

function domain(label: string, to: string): BreadcrumbItem {
  return { label, to };
}

const ROUTE_CRUMBS: BreadcrumbRoute[] = [
  {
    path: "/dashboard",
    crumbs: [domain("仪表盘", "/dashboard"), { label: "总览" }],
  },
  {
    path: "/ai-generation",
    crumbs: [domain("AI 生成", "/ai-generation"), { label: "生成工作台" }],
  },
  {
    path: "/ai-generation/history",
    crumbs: [domain("AI 生成", "/ai-generation"), { label: "生成历史" }],
  },
  {
    path: "/ai-generation/prompts",
    crumbs: [domain("AI 生成", "/ai-generation"), { label: "提示词管理" }],
  },
  {
    path: "/cases/review",
    crumbs: [domain("测试资产", "/cases"), { label: "待审核用例" }],
  },
  {
    path: "/cases/versions",
    crumbs: [domain("测试资产", "/cases"), { label: "用例版本" }],
  },
  {
    path: "/cases/tags",
    crumbs: [domain("测试资产", "/cases"), { label: "标签治理" }],
  },
  {
    path: "/cases/:caseId",
    crumbs: [domain("测试资产", "/cases"), { label: "用例中心", to: "/cases" }, { label: "用例详情" }],
  },
  {
    path: "/cases",
    crumbs: [domain("测试资产", "/cases"), { label: "用例中心" }],
  },
  {
    path: "/assets/test-points/:assetId/matrix",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "测试点资产", to: withProject("/assets/test-points", searchParams) },
      { label: "覆盖矩阵" },
    ],
  },
  {
    path: "/assets/test-points/:assetId/edit",
    crumbs: ({ searchParams, params }) => [
      domain("测试资产", "/cases"),
      { label: "测试点资产", to: withProject("/assets/test-points", searchParams) },
      {
        label: "测试点资产详情",
        to: params.assetId ? withProject(`/assets/test-points/${encodeURIComponent(params.assetId)}`, searchParams) : undefined,
      },
      { label: "编辑资产" },
    ],
  },
  {
    path: "/assets/test-points/:assetId",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "测试点资产", to: withProject("/assets/test-points", searchParams) },
      { label: "测试点资产详情" },
    ],
  },
  {
    path: "/assets/test-points",
    crumbs: [domain("测试资产", "/cases"), { label: "测试点资产" }],
  },
  {
    path: "/assets/page-objects/recorder/sessions/:sessionId",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "录制回放详情" },
    ],
  },
  {
    path: "/assets/page-objects/recorder",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "页面对象录制" },
    ],
  },
  {
    path: "/assets/page-objects/new",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "新建页面对象" },
    ],
  },
  {
    path: "/assets/page-objects/:pageCode/edit",
    crumbs: ({ searchParams, params }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      {
        label: "元素治理",
        to: params.pageCode ? withProject(`/assets/page-objects/${encodeURIComponent(params.pageCode)}/elements`, searchParams) : undefined,
      },
      { label: "编辑页面对象" },
    ],
  },
  {
    path: "/assets/page-objects/:pageCode/elements/candidates/:groupKey",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "候选分组详情" },
    ],
  },
  {
    path: "/assets/page-objects/:pageCode/elements/history/:sessionId",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "录制回放详情" },
    ],
  },
  {
    path: "/assets/page-objects/:pageCode/elements/:elementCode",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "元素详情" },
    ],
  },
  {
    path: "/assets/page-objects/:pageCode/elements",
    crumbs: ({ searchParams }) => [
      domain("测试资产", "/cases"),
      { label: "页面对象", to: withProject("/assets/page-objects", searchParams) },
      { label: "元素治理" },
    ],
  },
  {
    path: "/assets/page-objects",
    crumbs: [domain("测试资产", "/cases"), { label: "页面对象" }],
  },
  {
    path: "/assets/api-contracts",
    crumbs: [domain("测试资产", "/cases"), { label: "接口契约" }],
  },
  {
    path: "/assets/data-templates",
    crumbs: [domain("测试资产", "/cases"), { label: "数据模板" }],
  },
  {
    path: "/execution/results/failures",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "失败分析" }],
  },
  {
    path: "/execution/results/context",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "上下文" }],
  },
  {
    path: "/execution/results/performance",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "性能分析" }],
  },
  {
    path: "/execution/results/allure",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "Allure 报告" }],
  },
  {
    path: "/execution/results/:executionId",
    crumbs: [
      domain("执行与报告", "/execution/results"),
      { label: "结果总览", to: "/execution/results" },
      { label: "执行报告详情" },
    ],
  },
  {
    path: "/execution/results",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "结果总览" }],
  },
  {
    path: "/execution/plans",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "执行计划" }],
  },
  {
    path: "/execution/runs",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "执行记录" }],
  },
  {
    path: "/execution/workbench",
    crumbs: [domain("执行与报告", "/execution/results"), { label: "调试工作台" }],
  },
  {
    path: "/quality/flaky",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "Flaky 分析" }],
  },
  {
    path: "/quality/failure-clusters",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "失败聚类" }],
  },
  {
    path: "/quality/clusters",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "失败聚类" }],
  },
  {
    path: "/quality/trends",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "趋势分析" }],
  },
  {
    path: "/quality/gates",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "质量门禁" }],
  },
  {
    path: "/defects",
    crumbs: [domain("质量治理", "/quality/trends"), { label: "缺陷看板" }],
  },
  {
    path: "/system/projects",
    crumbs: [domain("系统设置", "/system/projects"), { label: "项目管理" }],
  },
  {
    path: "/system/source-config",
    crumbs: [domain("系统设置", "/system/projects"), { label: "源码管理" }],
  },
  {
    path: "/settings/scheduler",
    crumbs: [domain("系统设置", "/system/projects"), { label: "任务调度" }],
  },
  {
    path: "/system/environments",
    crumbs: [domain("系统设置", "/system/projects"), { label: "环境管理" }],
  },
  {
    path: "/system/nodes",
    crumbs: [domain("系统设置", "/system/projects"), { label: "节点管理" }],
  },
  {
    path: "/system/integrations",
    crumbs: [domain("系统设置", "/system/projects"), { label: "集成配置" }],
  },
  {
    path: "/system/roles",
    crumbs: [domain("系统设置", "/system/projects"), { label: "权限角色" }],
  },
];

function buildFallbackCrumbs(pathname: string): BreadcrumbItem[] {
  if (!pathname || pathname === "/") {
    return [];
  }
  return [{ label: pathname }];
}

function resolveCrumbs(pathname: string, search: string): BreadcrumbItem[] {
  const searchParams = new URLSearchParams(search);
  for (const route of ROUTE_CRUMBS) {
    const matched = matchPath({ path: route.path, end: true }, pathname);
    if (!matched) {
      continue;
    }
    const context: RouteCrumbContext = {
      pathname,
      searchParams,
      params: matched.params,
    };
    return typeof route.crumbs === "function" ? route.crumbs(context) : route.crumbs;
  }
  return buildFallbackCrumbs(pathname);
}

export function Breadcrumbs() {
  const location = useLocation();
  const crumbs = resolveCrumbs(location.pathname, location.search);

  if (crumbs.length === 0) {
    return null;
  }

  return (
    <nav className="platform-breadcrumbs" aria-label="面包屑">
      <ol>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={`${crumb.label}-${index}`} aria-current={isLast ? "page" : undefined}>
              {!isLast && crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span>{crumb.label}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
