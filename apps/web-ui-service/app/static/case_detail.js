(function () {
  const shell = document.getElementById("case-detail-shell");
  if (!shell) return;
  const caseId = Number(shell.getAttribute("data-case-id"));
  if (!caseId) return;
  const state = {
    versions: [],
  };

  const els = {
    detailTitle: document.getElementById("detail-title"),
    basicInfo: document.getElementById("basic-info"),
    scriptEditor: document.getElementById("script-editor"),
    scriptHighlight: document.getElementById("script-highlight"),
    defectList: document.getElementById("defect-list"),
    historyBody: document.getElementById("history-body"),
    versionBody: document.getElementById("version-body"),
    btnSaveScript: document.getElementById("btn-save-script"),
    btnAddDefect: document.getElementById("btn-add-defect"),
    versionFrom: document.getElementById("version-from"),
    versionTo: document.getElementById("version-to"),
    btnCompareVersion: document.getElementById("btn-compare-version"),
    versionDiffSummary: document.getElementById("version-diff-summary"),
    versionDiffViewer: document.getElementById("version-diff-viewer"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString("zh-CN");
    } catch (_error) {
      return String(value);
    }
  }

  function resultClass(status) {
    const normalized = String(status || "unknown").toLowerCase();
    if (normalized === "passed") return "result-passed";
    if (normalized === "failed") return "result-failed";
    if (normalized === "skipped") return "result-skipped";
    return "result-unknown";
  }

  function highlightPython(codeText) {
    let html = escapeHtml(codeText);
    html = html.replace(/(\".*?\"|\'.*?\')/g, '<span class="str">$1</span>');
    html = html.replace(/\b(def|class|return|if|elif|else|for|while|import|from|try|except|assert|with|as|pass|True|False|None)\b/g, '<span class="kw">$1</span>');
    html = html.replace(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g, '<span class="fn">$1</span>');
    return html;
  }

  function renderBasicInfo(basic) {
    const rows = [
      ["名称", basic.name],
      ["产品线", basic.product_line],
      ["模块", basic.module],
      ["优先级", basic.priority],
      ["标签", (basic.tags || []).join(", ") || "-"],
      ["创建人", basic.creator],
      ["最后执行结果", basic.last_execution_result],
      ["创建时间", formatTime(basic.created_at)],
      ["更新时间", formatTime(basic.updated_at)],
    ];
    els.basicInfo.innerHTML = rows
      .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
      .join("");
  }

  function renderDefects(defects) {
    if (!defects.length) {
      els.defectList.innerHTML = "<li>暂无关联缺陷</li>";
      return;
    }
    els.defectList.innerHTML = defects
      .map((item) => {
        const key = escapeHtml(item.defect_key);
        const url = escapeHtml(item.defect_url || "");
        if (url) {
          return `<li><a href="${url}" target="_blank" rel="noreferrer">${key}</a> <span class="muted">(${formatTime(item.created_at)})</span></li>`;
        }
        return `<li>${key} <span class="muted">(${formatTime(item.created_at)})</span></li>`;
      })
      .join("");
  }

  function renderHistory(executions) {
    if (!executions.length) {
      els.historyBody.innerHTML = '<tr><td colspan="4">暂无执行记录</td></tr>';
      return;
    }
    els.historyBody.innerHTML = executions
      .map(
        (item) => `
          <tr>
            <td>${formatTime(item.executed_at)}</td>
            <td><span class="result-pill ${resultClass(item.status)}">${escapeHtml(item.status)}</span></td>
            <td>${escapeHtml(item.duration_ms)}</td>
            <td>${item.report_url ? `<a href="${escapeHtml(item.report_url)}" target="_blank" rel="noreferrer">查看报告</a>` : "-"}</td>
          </tr>
        `
      )
      .join("");
  }

  function renderVersions(versions) {
    state.versions = versions.slice();
    if (!versions.length) {
      els.versionBody.innerHTML = '<tr><td colspan="4">暂无版本记录</td></tr>';
      if (els.versionFrom) {
        els.versionFrom.innerHTML = '<option value="">暂无版本</option>';
      }
      if (els.versionTo) {
        els.versionTo.innerHTML = '<option value="">暂无版本</option>';
      }
      return;
    }
    els.versionBody.innerHTML = versions
      .map(
        (item) => `
          <tr>
            <td>v${escapeHtml(item.version_no)}</td>
            <td>${escapeHtml(item.change_summary || "-")}</td>
            <td>${escapeHtml(item.changed_by || "-")}</td>
            <td>${formatTime(item.created_at)}</td>
          </tr>
        `
      )
      .join("");
    syncVersionSelectors();
  }

  function syncVersionSelectors() {
    if (!els.versionFrom || !els.versionTo) return;
    const versions = state.versions;
    if (!versions.length) return;

    const options = versions
      .map((item) => `<option value="${escapeHtml(item.version_no)}">v${escapeHtml(item.version_no)}</option>`)
      .join("");

    const previousFrom = Number(els.versionFrom.value);
    const previousTo = Number(els.versionTo.value);
    els.versionFrom.innerHTML = options;
    els.versionTo.innerHTML = options;

    const latest = versions[0]?.version_no;
    const previous = versions[1]?.version_no || latest;
    const fromFallback = previous;
    const toFallback = latest;

    const allVersionNos = new Set(versions.map((item) => Number(item.version_no)));
    els.versionFrom.value = allVersionNos.has(previousFrom) ? String(previousFrom) : String(fromFallback);
    els.versionTo.value = allVersionNos.has(previousTo) ? String(previousTo) : String(toFallback);
  }

  function renderVersionDiff(diffLines) {
    if (!els.versionDiffViewer) return;
    if (!diffLines || !diffLines.length) {
      els.versionDiffViewer.textContent = "两个版本脚本一致，没有差异。";
      return;
    }
    els.versionDiffViewer.innerHTML = diffLines
      .map((line) => {
        let cls = "";
        if (line.startsWith("+++") || line.startsWith("---")) cls = "diff-meta";
        else if (line.startsWith("@@")) cls = "diff-chunk";
        else if (line.startsWith("+")) cls = "diff-added";
        else if (line.startsWith("-")) cls = "diff-removed";
        return `<span class="${cls}">${escapeHtml(line)}</span>`;
      })
      .join("");
  }

  async function compareVersions(options = { silent: false }) {
    if (!els.versionFrom || !els.versionTo) return;
    const fromVersion = Number(els.versionFrom.value);
    const toVersion = Number(els.versionTo.value);
    if (!fromVersion || !toVersion) {
      if (!options.silent) {
        alert("请选择起始版本和目标版本。");
      }
      return;
    }
    const response = await fetch(
      `/api/test-cases/${caseId}/versions/compare?from_version=${fromVersion}&to_version=${toVersion}`
    );
    if (!response.ok) {
      if (!options.silent) {
        alert("版本对比失败。");
      }
      return;
    }
    const payload = await response.json();
    if (els.versionDiffSummary) {
      els.versionDiffSummary.textContent = `v${payload.from_version} -> v${payload.to_version}，新增 ${payload.added_lines} 行，删除 ${payload.removed_lines} 行。`;
    }
    renderVersionDiff(payload.diff_lines || []);
  }

  async function loadDetail() {
    const response = await fetch(`/api/test-cases/${caseId}`);
    if (!response.ok) {
      throw new Error("load detail failed");
    }
    const payload = await response.json();
    const basic = payload.basic || {};
    els.detailTitle.textContent = `用例详情 #${basic.id || caseId} - ${basic.name || ""}`;
    renderBasicInfo(basic);
    els.scriptEditor.value = payload.script_code || "";
    els.scriptHighlight.innerHTML = highlightPython(els.scriptEditor.value);
    renderDefects(payload.defects || []);
    renderHistory(payload.executions || []);
    renderVersions(payload.versions || []);
    if ((payload.versions || []).length > 0) {
      await compareVersions({ silent: true });
    }
  }

  async function saveScript() {
    const scriptCode = els.scriptEditor.value;
    if (!scriptCode.trim()) {
      alert("脚本不能为空。");
      return;
    }
    const response = await fetch(`/api/test-cases/${caseId}/script`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ script_code: scriptCode, changed_by: "admin" }),
    });
    if (!response.ok) {
      alert("保存脚本失败");
      return;
    }
    await loadDetail();
    alert("脚本已保存并生成新版本。");
  }

  async function addDefect() {
    const defectKey = window.prompt("请输入缺陷单号（如 BUG-4001）：", "");
    if (!defectKey) return;
    const defectUrl = window.prompt("请输入缺陷链接（可选）：", "") || "";
    const query = new URLSearchParams({ defect_key: defectKey, defect_url: defectUrl });
    const response = await fetch(`/api/test-cases/${caseId}/defects?${query}`, { method: "POST" });
    if (!response.ok) {
      alert("添加缺陷失败");
      return;
    }
    await loadDetail();
  }

  function bindEvents() {
    els.scriptEditor.addEventListener("input", () => {
      els.scriptHighlight.innerHTML = highlightPython(els.scriptEditor.value);
    });
    els.btnSaveScript.addEventListener("click", saveScript);
    els.btnAddDefect.addEventListener("click", addDefect);
    if (els.btnCompareVersion) {
      els.btnCompareVersion.addEventListener("click", () => {
        compareVersions().catch((error) => {
          console.error(error);
          alert("版本对比失败。");
        });
      });
    }
  }

  bindEvents();
  loadDetail().catch((error) => {
    console.error(error);
    alert("加载用例详情失败。");
  });
})();
