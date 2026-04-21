import { Navigate, Route, Routes } from "react-router-dom";

import { AiGenerationHistoryPage } from "./pages/AiGenerationHistoryPage";
import { AiGenerationPage } from "./pages/AiGenerationPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CasesPage } from "./pages/CasesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DefectsPage } from "./pages/DefectsPage";
import { ExecutionPlansPage } from "./pages/ExecutionPlansPage";
import { ExecutionResultDetailPage } from "./pages/ExecutionResultDetailPage";
import { ExecutionRunsPage } from "./pages/ExecutionRunsPage";
import { LoginPage } from "./pages/LoginPage";
import { ManagementConsolePage } from "./pages/ManagementConsolePage";
import { PageObjectRecorderPage } from "./pages/PageObjectRecorderPage";
import { PageObjectsPage } from "./pages/PageObjectsPage";
import { PromptManagementPage } from "./pages/PromptManagementPage";
import { QualityClustersPage } from "./pages/QualityClustersPage";
import { QualityFlakyPage } from "./pages/QualityFlakyPage";
import { QualityGatesPage } from "./pages/QualityGatesPage";
import { QualityTrendsPage } from "./pages/QualityTrendsPage";
import { ReportAllurePage } from "./pages/ReportAllurePage";
import { ReportContextPage } from "./pages/ReportContextPage";
import { ReportFailuresPage } from "./pages/ReportFailuresPage";
import { ReportOverviewPage } from "./pages/ReportOverviewPage";
import { ReportPerformancePage } from "./pages/ReportPerformancePage";
import { SchedulerPage } from "./pages/SchedulerPage";
import { TestPointAssetDetailPage } from "./pages/TestPointAssetDetailPage";
import { TestPointAssetsPage } from "./pages/TestPointAssetsPage";

function NotFound() {
  return (
    <main className="page shell">
      <section className="panel">
        <h1>页面不存在</h1>
        <p>请返回仪表盘继续操作。</p>
        <a className="button" href="/react/dashboard">
          打开仪表盘
        </a>
      </section>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/ai-generation" element={<AiGenerationPage />} />
      <Route path="/ai-generation/history" element={<AiGenerationHistoryPage />} />
      <Route path="/ai-generation/prompts" element={<PromptManagementPage />} />
      <Route path="/cases" element={<CasesPage />} />
      <Route path="/cases/:caseId" element={<CaseDetailPage />} />
      <Route
        path="/cases/review"
        element={
          <ManagementConsolePage
            title="待审核用例（React + TypeScript）"
            description="统一承接待审核队列与审核动作入口。"
            primaryLabel="进入用例列表"
            primaryHref="/cases"
            secondaryLabel="查看用例版本"
            secondaryHref="/cases/versions"
          />
        }
      />
      <Route
        path="/cases/versions"
        element={
          <ManagementConsolePage
            title="用例版本（React + TypeScript）"
            description="统一管理版本链路、变更摘要和回滚入口。"
            primaryLabel="返回用例列表"
            primaryHref="/cases"
          />
        }
      />
      <Route
        path="/cases/tags"
        element={
          <ManagementConsolePage
            title="标签治理（React + TypeScript）"
            description="统一承接标签分类、治理规则和标签资产维护。"
            primaryLabel="进入用例列表"
            primaryHref="/cases"
          />
        }
      />
      <Route path="/assets/test-points" element={<TestPointAssetsPage />} />
      <Route path="/assets/test-points/:assetId" element={<TestPointAssetDetailPage />} />
      <Route path="/assets/test-points/:assetId/matrix" element={<TestPointAssetDetailPage />} />
      <Route path="/assets/page-objects" element={<PageObjectsPage />} />
      <Route path="/assets/page-objects/recorder" element={<PageObjectRecorderPage />} />
      <Route
        path="/assets/api-contracts"
        element={
          <ManagementConsolePage
            title="接口契约（React + TypeScript）"
            description="统一管理 API 契约资产、差异分析和校验记录。"
            primaryLabel="查看测试点资产"
            primaryHref="/assets/test-points"
          />
        }
      />
      <Route
        path="/assets/data-templates"
        element={
          <ManagementConsolePage
            title="数据模板（React + TypeScript）"
            description="统一维护数据模板、样本配置和导出能力。"
            primaryLabel="查看测试点资产"
            primaryHref="/assets/test-points"
          />
        }
      />
      <Route path="/quality/flaky" element={<QualityFlakyPage />} />
      <Route path="/quality/failure-clusters" element={<QualityClustersPage />} />
      <Route path="/quality/clusters" element={<Navigate to="/quality/failure-clusters" replace />} />
      <Route path="/quality/trends" element={<QualityTrendsPage />} />
      <Route path="/quality/gates" element={<QualityGatesPage />} />
      <Route path="/defects" element={<DefectsPage />} />
      <Route path="/settings/scheduler" element={<SchedulerPage />} />
      <Route
        path="/system/environments"
        element={
          <ManagementConsolePage
            title="环境管理（React + TypeScript）"
            description="统一承接环境配置、连接校验和运行策略。"
          />
        }
      />
      <Route
        path="/system/nodes"
        element={
          <ManagementConsolePage
            title="节点管理（React + TypeScript）"
            description="统一管理执行节点、容量信息和健康状态。"
          />
        }
      />
      <Route
        path="/system/integrations"
        element={
          <ManagementConsolePage
            title="集成配置（React + TypeScript）"
            description="统一管理第三方系统对接和回调设置。"
          />
        }
      />
      <Route
        path="/system/roles"
        element={
          <ManagementConsolePage
            title="权限与角色（React + TypeScript）"
            description="统一管理角色权限、审核边界和访问控制。"
            primaryLabel="查看环境管理"
            primaryHref="/system/environments"
          />
        }
      />
      <Route path="/execution/plans" element={<ExecutionPlansPage />} />
      <Route
        path="/execution/workbench"
        element={
          <ManagementConsolePage
            title="调试工作台（React + TypeScript）"
            description="统一承接高级调试、复现与重跑能力。"
            primaryLabel="打开执行记录"
            primaryHref="/execution/runs"
            secondaryLabel="返回 AI 生成"
            secondaryHref="/ai-generation"
          />
        }
      />
      <Route path="/execution/runs" element={<ExecutionRunsPage />} />
      <Route path="/execution/results" element={<ReportOverviewPage />} />
      <Route path="/execution/results/:executionId" element={<ExecutionResultDetailPage />} />
      <Route path="/execution/results/failures" element={<ReportFailuresPage />} />
      <Route path="/execution/results/context" element={<ReportContextPage />} />
      <Route path="/execution/results/performance" element={<ReportPerformancePage />} />
      <Route path="/execution/results/allure" element={<ReportAllurePage />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
