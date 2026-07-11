import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  applyPageObjectImport,
  previewPageObjectImport,
} from "../api/assets";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { MetricCards } from "../components/MetricCards";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function numberOf(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(String(value || "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatFileSize(value: unknown): string {
  const size = numberOf(value);
  if (size <= 0) {
    return "0 B";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function actionLabel(value: unknown): string {
  const normalized = String(value || "").trim();
  const labels: Record<string, string> = {
    create: "新增",
    upgrade: "升级",
    skip: "跳过",
    conflict: "冲突",
  };
  return labels[normalized] || text(normalized);
}

function actionTone(value: unknown): string {
  const normalized = String(value || "").trim();
  if (normalized === "create") {
    return "success";
  }
  if (normalized === "upgrade") {
    return "warn";
  }
  if (normalized === "conflict") {
    return "danger";
  }
  return "";
}

function buildBackLink(projectCode: string): string {
  const query = new URLSearchParams();
  if (projectCode) {
    query.set("project", projectCode);
  }
  return `/assets/page-objects${query.toString() ? `?${query.toString()}` : ""}`;
}

export function PageObjectImportPage() {
  const [searchParams] = useSearchParams();
  const [projectCode, setProjectCode] = useState<string>(normalizeProjectCode(searchParams.get("project") || DEFAULT_PROJECT_CODE));
  const [pageCode, setPageCode] = useState<string>(String(searchParams.get("page_code") || "").trim());
  const [sourceType, setSourceType] = useState<"data_testid_guidelines" | "data_testid_inventory">("data_testid_inventory");
  const [dataTestidFile, setDataTestidFile] = useState<File | null>(null);
  const [runtimeDomFile, setRuntimeDomFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [applyResult, setApplyResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [step, setStep] = useState<1 | 2 | 3>(1);

  const summary = useMemo(() => {
    const row = (preview?.summary || {}) as Record<string, unknown>;
    return {
      pageCount: numberOf(row.page_count),
      elementCount: numberOf(row.element_count),
      createCount: numberOf(row.create_count),
      upgradeCount: numberOf(row.upgrade_count),
      conflictCount: numberOf(row.conflict_count),
      templateCount: numberOf(row.template_count),
    };
  }, [preview]);

  const elements = useMemo(() => (Array.isArray(preview?.elements) ? preview.elements as Array<Record<string, unknown>> : []), [preview]);
  const pages = useMemo(() => (Array.isArray(preview?.pages) ? preview.pages as Array<Record<string, unknown>> : []), [preview]);
  const result = (applyResult?.apply_result || {}) as Record<string, unknown>;

  async function handlePreview() {
    if (!dataTestidFile) {
      setErrorText("请先上传 data-testid 清单。");
      return;
    }
    if (dataTestidFile.size <= 0) {
      setErrorText("data-testid 清单文件为空，请重新选择有效的 Markdown 文件。");
      return;
    }
    setBusy(true);
    setErrorText("");
    setApplyResult(null);
    try {
      const payload = await previewPageObjectImport({
        project_code: projectCode,
        client: "web",
        source_type: sourceType,
        page_code: pageCode,
        data_testid_guidelines: dataTestidFile,
        runtime_dom_selectors: runtimeDomFile,
      });
      setPreview(payload.item || null);
      setStep(2);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "导入预览失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    const importId = String(preview?.import_id || "").trim();
    if (!importId) {
      setErrorText("缺少导入批次，请重新预览。");
      return;
    }
    setBusy(true);
    setErrorText("");
    try {
      const payload = await applyPageObjectImport(importId, {
        auto_approve: true,
        upsert_policy: "upgrade_existing",
        operator: "admin",
      });
      setApplyResult(payload.item || null);
      setStep(3);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "确认入库失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>导入页面对象</h1>
          <p className="muted">通过被测系统源码扫描出的真实 data-testid 清单，批量创建或升级页面对象元素。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={buildBackLink(projectCode)}>
            返回页面对象
          </Link>
        </div>
      </header>

      <section className="panel">
        <div className="header-actions">
          <span className={`count-badge ${step === 1 ? "success" : ""}`}>1 上传文件</span>
          <span className={`count-badge ${step === 2 ? "success" : ""}`}>2 解析预览</span>
          <span className={`count-badge ${step === 3 ? "success" : ""}`}>3 确认入库</span>
        </div>
      </section>

      <section className="panel">
        <div className="form-grid">
          <label>
            项目编码
            <input value={projectCode} onChange={(event) => setProjectCode(normalizeProjectCode(event.target.value))} disabled={busy} />
          </label>
          <label>
            端类型
            <input value="web" disabled />
          </label>
          <label>
            仅导入指定页面
            <input value={pageCode} onChange={(event) => setPageCode(event.target.value.trim())} placeholder="可选，例如 login / product" disabled={busy} />
          </label>
          <label>
            清单格式
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value as typeof sourceType)} disabled={busy}>
              <option value="data_testid_inventory">data-testid-inventory.md（推荐）</option>
              <option value="data_testid_guidelines">data-testid-guidelines.md（兼容旧格式）</option>
            </select>
          </label>
          <label>
            权威清单
            <input
              type="file"
              accept=".md,text/markdown,text/plain"
              onChange={(event) => {
                const file = event.target.files?.[0] || null;
                setDataTestidFile(file);
                setPreview(null);
                setApplyResult(null);
                if (file && file.size <= 0) {
                  setErrorText("data-testid 清单文件为空，请重新选择有效的 Markdown 文件。");
                } else {
                  setErrorText("");
                }
              }}
              disabled={busy}
            />
            <small>
              {sourceType === "data_testid_inventory"
                ? "必填：data-testid-inventory.md，解析“按页面汇总”中的 data-testid 表格。"
                : "必填：data-testid-guidelines.md，只解析“已落地清单”。"}
              {dataTestidFile ? ` 当前文件：${dataTestidFile.name} / ${formatFileSize(dataTestidFile.size)}` : ""}
            </small>
          </label>
          <label>
            运行态 DOM 校验
            <input
              type="file"
              accept=".json,application/json"
              onChange={(event) => setRuntimeDomFile(event.target.files?.[0] || null)}
              disabled={busy}
            />
            <small>
              可选：runtime-dom-selectors.json，v1 仅记录为辅助材料。
              {runtimeDomFile ? ` 当前文件：${runtimeDomFile.name} / ${formatFileSize(runtimeDomFile.size)}` : ""}
            </small>
          </label>
        </div>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void handlePreview()} disabled={busy || !dataTestidFile || dataTestidFile.size <= 0}>
            解析预览
          </button>
          <span className="muted">被测系统原始地址不会在导入中被改写。</span>
        </div>
      </section>

      {errorText ? <section className="panel error">{errorText}</section> : null}
      {busy ? <section className="panel">正在处理导入任务...</section> : null}

      {preview ? (
        <>
          <MetricCards
            items={[
              { label: "页面数", value: summary.pageCount, hint: "本次清单覆盖的页面对象" },
              { label: "元素数", value: summary.elementCount, hint: "解析出的真实 data-testid" },
              { label: "新增", value: summary.createCount, hint: "正式元素库中不存在", tone: "good" },
              { label: "升级", value: summary.upgradeCount, hint: "已有元素升级为 data-testid", tone: "warn" },
              { label: "冲突", value: summary.conflictCount, hint: "重复或需要人工处理", tone: summary.conflictCount ? "bad" : "" },
              { label: "动态模板", value: summary.templateCount, hint: "不会作为普通步骤默认候选" },
            ]}
          />

          <DataTable title={`页面级摘要：${pages.length}`}>
            <table>
              <thead>
                <tr>
                  <th>页面编码</th>
                  <th>页面名称</th>
                  <th>源码路径</th>
                  <th>元素数</th>
                  <th>新增</th>
                  <th>升级</th>
                  <th>冲突</th>
                  <th>动态模板</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((item, index) => (
                  <tr key={`${item.page_code || index}`}>
                    <td className="mono">{text(item.page_code)}</td>
                    <td>{text(item.page_name)}</td>
                    <td className="compact-cell">{text(item.source_path)}</td>
                    <td>{text(item.element_count)}</td>
                    <td>{text(item.create_count)}</td>
                    <td>{text(item.upgrade_count)}</td>
                    <td>{text(item.conflict_count)}</td>
                    <td>{text(item.template_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTable>

          <DataTable title={`元素差异清单：${elements.length}`}>
            <table>
              <thead>
                <tr>
                  <th>动作</th>
                  <th>页面</th>
                  <th>元素编码</th>
                  <th>元素名称</th>
                  <th>data-testid</th>
                  <th>类型</th>
                  <th>策略</th>
                  <th>关键元素</th>
                  <th>名称动作</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {elements.length ? (
                  elements.slice(0, 300).map((item, index) => (
                    <tr key={`${item.page_code || ""}-${item.element_code || index}`}>
                      <td><span className={`count-badge ${actionTone(item.action)}`}>{actionLabel(item.action)}</span></td>
                      <td className="mono">{text(item.page_code)}</td>
                      <td className="mono">{text(item.element_code)}</td>
                      <td>{text(item.element_name)}</td>
                      <td className="mono">{text(item.testid)}</td>
                      <td>{text(item.business_type)}</td>
                      <td>{text(item.match_strategy)}</td>
                      <td>{item.is_key_element ? "是" : "否"}</td>
                      <td>{text(item.name_action || "-")}</td>
                      <td>{text(item.reason)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={10}>
                      <EmptyState title="暂无元素差异" description="请重新上传清单并解析。" />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </DataTable>

          <section className="panel">
            <div className="header-actions">
              <button type="button" className="button" onClick={() => void handleApply()} disabled={busy || summary.conflictCount > 0}>
                确认入库
              </button>
              {summary.conflictCount > 0 ? <span className="muted">存在冲突元素时需要先修正清单后再导入。</span> : null}
            </div>
          </section>
        </>
      ) : null}

      {applyResult ? (
        <section className="panel">
          <h2>入库完成</h2>
          <p className="muted">页面对象和正式元素已刷新，真实 data-testid 已自动标记为 approved / high。</p>
          <div className="header-actions">
            <span className="count-badge success">新建页面 {text(result.created_page_count)}</span>
            <span className="count-badge success">新增元素 {text(result.created_element_count)}</span>
            <span className="count-badge warn">升级元素 {text(result.upgraded_element_count)}</span>
            <span className="count-badge">跳过 {text(result.skipped_element_count)}</span>
            <Link className="button secondary" to={buildBackLink(projectCode)}>
              查看页面对象列表
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
