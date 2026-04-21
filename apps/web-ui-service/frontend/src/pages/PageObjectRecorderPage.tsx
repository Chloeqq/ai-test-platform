import { useState } from "react";
import { Link } from "react-router-dom";

import { createRecorderSession, heartbeatRecorderSession, stopRecorderSession } from "../api/assets";

interface RecorderForm {
  project_code: string;
  client: string;
  page_code: string;
  page_name: string;
  url: string;
  started_by: string;
}

const DEFAULT_FORM: RecorderForm = {
  project_code: "atp",
  client: "web",
  page_code: "",
  page_name: "",
  url: "",
  started_by: "admin",
};

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

export function PageObjectRecorderPage() {
  const [form, setForm] = useState<RecorderForm>(DEFAULT_FORM);
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [payload, setPayload] = useState<Record<string, unknown>>({});

  async function handleCreate() {
    if (loading) {
      return;
    }
    if (!form.page_code.trim() || !form.page_name.trim() || !form.url.trim()) {
      setFeedback("page_code/page_name/url 为必填。");
      return;
    }
    setLoading(true);
    setFeedback("正在创建录制会话...");
    try {
      const response = await createRecorderSession({
        project_code: form.project_code.trim() || "atp",
        client: form.client.trim() || "web",
        page_code: form.page_code.trim(),
        page_name: form.page_name.trim(),
        url: form.url.trim(),
        started_by: form.started_by.trim() || "admin",
      });
      const item = (response.item || {}) as Record<string, unknown>;
      const nextSessionId = String(item.session_id || item.id || "").trim();
      setSessionId(nextSessionId);
      setPayload(item);
      setFeedback(nextSessionId ? `会话已创建：${nextSessionId}` : "会话已创建");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "创建会话失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleHeartbeat() {
    if (loading || !sessionId.trim()) {
      return;
    }
    setLoading(true);
    setFeedback("正在发送心跳...");
    try {
      const response = await heartbeatRecorderSession(sessionId.trim(), {
        heartbeat_by: form.started_by.trim() || "admin",
      });
      const item = (response.item || {}) as Record<string, unknown>;
      setPayload(item);
      setFeedback("心跳已更新。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "心跳失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    if (loading || !sessionId.trim()) {
      return;
    }
    setLoading(true);
    setFeedback("正在停止会话并处理录制产物...");
    try {
      const response = await stopRecorderSession(sessionId.trim(), {
        ingest_to_page_object: true,
        cascade_elements: false,
        verify_locators: false,
        verify_timeout_ms: 4000,
        changed_by: form.started_by.trim() || "admin",
      });
      setPayload((response || {}) as Record<string, unknown>);
      setFeedback("会话已停止。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "停止会话失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>页面对象录制（React + TypeScript）</h1>
          <p className="muted">调用后端 recorder API 托管录制会话。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/assets/page-objects">
            返回页面对象
          </Link>
        </div>
      </header>

      <section className="panel form-grid">
        <label>
          project_code
          <input value={form.project_code} onChange={(event) => setForm((prev) => ({ ...prev, project_code: event.target.value }))} />
        </label>
        <label>
          client
          <input value={form.client} onChange={(event) => setForm((prev) => ({ ...prev, client: event.target.value }))} />
        </label>
        <label>
          started_by
          <input value={form.started_by} onChange={(event) => setForm((prev) => ({ ...prev, started_by: event.target.value }))} />
        </label>
        <label>
          page_code
          <input value={form.page_code} onChange={(event) => setForm((prev) => ({ ...prev, page_code: event.target.value }))} />
        </label>
        <label>
          page_name
          <input value={form.page_name} onChange={(event) => setForm((prev) => ({ ...prev, page_name: event.target.value }))} />
        </label>
        <label className="span-3">
          url
          <input value={form.url} onChange={(event) => setForm((prev) => ({ ...prev, url: event.target.value }))} />
        </label>
      </section>

      <section className="panel header-actions">
        <button type="button" className="button" onClick={() => void handleCreate()} disabled={loading}>
          创建会话
        </button>
        <button type="button" className="button secondary" onClick={() => void handleHeartbeat()} disabled={loading || !sessionId.trim()}>
          发送心跳
        </button>
        <button type="button" className="button secondary" onClick={() => void handleStop()} disabled={loading || !sessionId.trim()}>
          停止会话
        </button>
      </section>

      <section className="panel">
        <p>
          <strong>session_id:</strong> <span className="mono">{text(sessionId)}</span>
        </p>
        <p>{text(feedback)}</p>
      </section>

      <section className="panel">
        <h2>返回结果</h2>
        <pre className="json-block">{JSON.stringify(payload || {}, null, 2)}</pre>
      </section>
    </main>
  );
}
