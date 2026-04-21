import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getPageObject, listPageElements, listPageObjects } from "../api/assets";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function numberValue(value: unknown): string {
  if (typeof value === "number") {
    return String(value);
  }
  const normalized = String(value || "").trim();
  return normalized || "0";
}

function formatDate(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

export function PageObjectsPage() {
  const [projectCode, setProjectCode] = useState<string>("atp");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectedPageCode, setSelectedPageCode] = useState<string>("");
  const [selectedObject, setSelectedObject] = useState<Record<string, unknown>>({});
  const [elements, setElements] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listPageObjects({ project_code: projectCode, client: "web" });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      const firstPageCode = selectedPageCode || String(rows[0]?.page_code || "").trim();
      setSelectedPageCode(firstPageCode);
      if (firstPageCode) {
        const [objectPayload, elementPayload] = await Promise.all([
          getPageObject(firstPageCode, { project_code: projectCode, client: "web" }),
          listPageElements(firstPageCode, { project_code: projectCode, client: "web" }),
        ]);
        setSelectedObject((objectPayload.item || {}) as Record<string, unknown>);
        setElements(Array.isArray(elementPayload.items) ? elementPayload.items : []);
      } else {
        setSelectedObject({});
        setElements([]);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象加载失败");
      setItems([]);
      setSelectedObject({});
      setElements([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectCode]);

  async function selectPage(pageCode: string) {
    const normalized = String(pageCode || "").trim();
    if (!normalized) {
      return;
    }
    setSelectedPageCode(normalized);
    try {
      const [objectPayload, elementPayload] = await Promise.all([
        getPageObject(normalized, { project_code: projectCode, client: "web" }),
        listPageElements(normalized, { project_code: projectCode, client: "web" }),
      ]);
      setSelectedObject((objectPayload.item || {}) as Record<string, unknown>);
      setElements(Array.isArray(elementPayload.items) ? elementPayload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象详情加载失败");
      setSelectedObject({});
      setElements([]);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>页面对象（React + TypeScript）</h1>
          <p className="muted">统一查看页面对象与元素映射。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/assets/page-objects/recorder">
            页面录制
          </Link>
        </div>
      </header>

      <section className="panel filters">
        <label>
          project_code
          <input value={projectCode} onChange={(event) => setProjectCode(event.target.value)} />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload()}>
            刷新
          </button>
        </div>
      </section>

      {loading ? <section className="panel">正在加载页面对象...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}

      {!loading && !errorText ? (
        <section className="panel table-panel">
          <div className="table-head">
            <strong>页面对象列表：{items.length}</strong>
          </div>
          <table>
            <thead>
              <tr>
                <th>page_code</th>
                <th>page_name</th>
                <th>status</th>
                <th>element_count</th>
                <th>updated_at</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item, index) => {
                  const pageCode = String(item.page_code || "").trim();
                  return (
                    <tr key={String(item.id || index)} className={pageCode === selectedPageCode ? "is-active" : ""}>
                      <td className="mono">{text(pageCode)}</td>
                      <td>{text(item.page_name)}</td>
                      <td>{text(item.status)}</td>
                      <td>{numberValue(item.element_count)}</td>
                      <td>{formatDate(item.updated_at)}</td>
                      <td>
                        <button type="button" className="button secondary" onClick={() => void selectPage(pageCode)}>
                          查看元素
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6}>暂无页面对象。</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="panel table-panel">
          <div className="table-head">
            <strong>元素列表（{text(selectedObject.page_code)}）</strong>
          </div>
          <table>
            <thead>
              <tr>
                <th>element_code</th>
                <th>element_name</th>
                <th>locator_type</th>
                <th>locator_value</th>
                <th>status</th>
              </tr>
            </thead>
            <tbody>
              {elements.length ? (
                elements.map((item, index) => (
                  <tr key={String(item.element_id || index)}>
                    <td className="mono">{text(item.element_code)}</td>
                    <td>{text(item.element_name)}</td>
                    <td>{text(item.locator_type)}</td>
                    <td className="mono">{text(item.locator_value)}</td>
                    <td>{text(item.status)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>暂无元素记录。</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
