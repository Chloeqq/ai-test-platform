import { Link, Navigate, Route, Routes } from "react-router-dom";
import { GlobalNavLayout } from "./components/GlobalNavLayout";

import { AiGenerationHistoryPage } from "./pages/AiGenerationHistoryPage";
import { AiGenerationPage } from "./pages/AiGenerationPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CaseGenerationFailuresPage } from "./pages/CaseGenerationFailuresPage";
import { CasesPage } from "./pages/CasesPage";
import { CasesReviewPage } from "./pages/CasesReviewPage";
import { CaseTagsPage } from "./pages/CaseTagsPage";
import { CaseVersionsPage } from "./pages/CaseVersionsPage";
import { ApiContractsPage } from "./pages/ApiContractsPage";
import { DataTemplatesPage } from "./pages/DataTemplatesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DefectsPage } from "./pages/DefectsPage";
import { ExecutionPlansPage } from "./pages/ExecutionPlansPage";
import { ExecutionResultDetailPage } from "./pages/ExecutionResultDetailPage";
import { ExecutionRunsPage } from "./pages/ExecutionRunsPage";
import { LoginPage } from "./pages/LoginPage";
import { ManagementConsolePage } from "./pages/ManagementConsolePage";
import { PageObjectRecorderPage } from "./pages/PageObjectRecorderPage";
import { PageObjectElementsPage } from "./pages/PageObjectElementsPage";
import { PageObjectEditPage } from "./pages/PageObjectEditPage";
import { PageObjectImportPage } from "./pages/PageObjectImportPage";
import { PageObjectsPage } from "./pages/PageObjectsPage";
import { PromptManagementPage } from "./pages/PromptManagementPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { QualityClustersPage } from "./pages/QualityClustersPage";
import { QualityDashboardPage } from "./pages/QualityDashboardPage";
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
import { TestPointAssetEditPage } from "./pages/TestPointAssetEditPage";
import { TestPointAssetsPage } from "./pages/TestPointAssetsPage";

function NotFound() {
  return (
    <main className="shell">
      <section className="panel">
        <h1>页面不存在</h1>
        <p>请返回仪表盘继续操作。</p>
        <Link className="button" to="/dashboard">
          打开仪表盘
        </Link>
      </section>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<GlobalNavLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/ai-generation" element={<AiGenerationPage />} />
        <Route path="/ai-generation/history" element={<AiGenerationHistoryPage />} />
        <Route path="/ai-generation/prompts" element={<PromptManagementPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/generation-failures" element={<CaseGenerationFailuresPage />} />
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/cases/review" element={<CasesReviewPage />} />
        <Route path="/cases/versions" element={<CaseVersionsPage />} />
        <Route path="/cases/tags" element={<CaseTagsPage />} />
        <Route path="/assets/test-points" element={<TestPointAssetsPage />} />
        <Route path="/assets/test-points/:assetId/edit" element={<TestPointAssetEditPage />} />
        <Route path="/assets/test-points/:assetId" element={<TestPointAssetDetailPage />} />
        <Route path="/assets/test-points/:assetId/matrix" element={<TestPointAssetDetailPage />} />
        <Route path="/assets/page-objects" element={<PageObjectsPage />} />
        <Route path="/assets/page-objects/import" element={<PageObjectImportPage />} />
        <Route path="/assets/page-objects/new" element={<PageObjectEditPage mode="create" />} />
        <Route path="/assets/page-objects/:pageCode/edit" element={<PageObjectEditPage mode="edit" />} />
        <Route path="/assets/page-objects/:pageCode/elements" element={<PageObjectElementsPage />} />
        <Route path="/assets/page-objects/:pageCode/elements/candidates/:groupKey" element={<PageObjectElementsPage />} />
        <Route path="/assets/page-objects/:pageCode/elements/history/:sessionId" element={<PageObjectElementsPage />} />
        <Route path="/assets/page-objects/:pageCode/elements/:elementCode" element={<PageObjectElementsPage />} />
        <Route path="/assets/page-objects/recorder" element={<PageObjectRecorderPage />} />
        <Route path="/assets/page-objects/recorder/sessions/:sessionId" element={<PageObjectRecorderPage />} />
        <Route path="/assets/api-contracts" element={<ApiContractsPage />} />
        <Route path="/assets/data-templates" element={<DataTemplatesPage />} />
        <Route path="/quality/dashboard" element={<QualityDashboardPage />} />
        <Route path="/quality/flaky" element={<QualityFlakyPage />} />
        <Route path="/quality/failure-clusters" element={<QualityClustersPage />} />
        <Route path="/quality/clusters" element={<Navigate to="/quality/failure-clusters" replace />} />
        <Route path="/quality/trends" element={<QualityTrendsPage />} />
        <Route path="/quality/gates" element={<QualityGatesPage />} />
        <Route path="/defects" element={<DefectsPage />} />
        <Route path="/settings/scheduler" element={<SchedulerPage />} />
        <Route
          path="/system/projects"
          element={<ProjectsPage />}
        />
        <Route
          path="/system/source-config"
          element={<ProjectsPage mode="source" />}
        />
        <Route
          path="/system/environments"
          element={
            <ManagementConsolePage
              title="环境管理"
              description="统一承接环境配置、连接校验和运行策略。"
            />
          }
        />
        <Route
          path="/system/nodes"
          element={
            <ManagementConsolePage
              title="节点管理"
              description="统一管理执行节点、容量信息和健康状态。"
            />
          }
        />
        <Route
          path="/system/integrations"
          element={
            <ManagementConsolePage
              title="集成配置"
              description="统一管理第三方系统对接和回调设置。"
            />
          }
        />
        <Route
          path="/system/roles"
          element={
            <ManagementConsolePage
              title="权限与角色"
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
              title="调试工作台"
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
      </Route>
    </Routes>
  );
}
