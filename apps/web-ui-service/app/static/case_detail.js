(function () {
  const shell = document.getElementById("case-detail-shell");
  if (!shell) return;
  const caseId = Number(shell.getAttribute("data-case-id"));
  if (!caseId) return;
  const state = {
    versions: [],
    dataConfig: {
      enabled: false,
      parameters: [],
      rows: [],
    },
  };

  const els = {
    detailTitle: document.getElementById("detail-title"),
    basicInfo: document.getElementById("basic-info"),
    btnSaveAssetMeta: document.getElementById("btn-save-asset-meta"),
    detailTestType: document.getElementById("detail-test-type"),
    detailStatus: document.getElementById("detail-status"),
    detailPytestPath: document.getElementById("detail-pytest-path"),
    detailMarkers: document.getElementById("detail-markers"),
    scriptEditor: document.getElementById("script-editor"),
    scriptHighlight: document.getElementById("script-highlight"),
    defectList: document.getElementById("defect-list"),
    historyBody: document.getElementById("history-body"),
    versionBody: document.getElementById("version-body"),
    btnSaveScript: document.getElementById("btn-save-script"),
    btnAddDefect: document.getElementById("btn-add-defect"),
    btnSaveDataConfig: document.getElementById("btn-save-data-config"),
    detailDdtEnabled: document.getElementById("detail-ddt-enabled"),
    detailDdtParameters: document.getElementById("detail-ddt-parameters"),
    detailDdtTableHead: document.getElementById("detail-ddt-table-head"),
    detailDdtTableBody: document.getElementById("detail-ddt-table-body"),
    btnDetailDdtAddRow: document.getElementById("btn-detail-ddt-add-row"),
    btnDetailDdtClearRows: document.getElementById("btn-detail-ddt-clear-rows"),
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

  function parseList(text) {
    return String(text || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function normalizeRows(parameters, rows) {
    const width = parameters.length;
    if (!width) return [];
    return (rows || [])
      .map((row) => (row || []).map((item) => String(item || "").trim()).slice(0, width))
      .map((row) => row.concat(Array(Math.max(0, width - row.length)).fill("")))
      .filter((row) => row.some((item) => item !== ""));
  }

  function refreshDataConfigFromForm() {
    state.dataConfig.enabled = Boolean(els.detailDdtEnabled.checked);
    state.dataConfig.parameters = parseList(els.detailDdtParameters.value);
    state.dataConfig.rows = normalizeRows(state.dataConfig.parameters, state.dataConfig.rows);
    renderDataConfigTable();
  }

  function renderDataConfigTable() {
    const parameters = state.dataConfig.parameters;
    const rows = state.dataConfig.rows;

    if (!parameters.length) {
      els.detailDdtTableHead.innerHTML = "";
      els.detailDdtTableBody.innerHTML = '<tr><td class="ddt-empty">请先填写参数。</td></tr>';
      return;
    }

    els.detailDdtTableHead.innerHTML = `<tr>${parameters.map((item) => `<th>${escapeHtml(item)}</th>`).join("")}<th class="ddt-row-action">操作</th></tr>`;
    if (!rows.length) {
      els.detailDdtTableBody.innerHTML = `<tr><td class="ddt-empty" colspan="${parameters.length + 1}">暂无数据行。</td></tr>`;
      return;
    }

    els.detailDdtTableBody.innerHTML = rows
      .map((row, rowIndex) => {
        const cells = row
          .map(
            (value, colIndex) =>
              `<td><input type="text" data-detail-ddt-row="${rowIndex}" data-detail-ddt-col="${colIndex}" value="${escapeHtml(value)}"></td>`
          )
          .join("");
        return `<tr>${cells}<td><button type="button" class="btn btn-danger" data-detail-ddt-remove="${rowIndex}">删除</button></td></tr>`;
      })
      .join("");

    els.detailDdtTableBody.querySelectorAll("input[data-detail-ddt-row]").forEach((input) => {
      input.addEventListener("input", () => {
        const row = Number(input.getAttribute("data-detail-ddt-row"));
        const col = Number(input.getAttribute("data-detail-ddt-col"));
        if (Number.isInteger(row) && Number.isInteger(col) && state.dataConfig.rows[row]) {
          state.dataConfig.rows[row][col] = input.value;
        }
      });
    });

    els.detailDdtTableBody.querySelectorAll("button[data-detail-ddt-remove]").forEach((button) => {
      button.addEventListener("click", () => {
        const row = Number(button.getAttribute("data-detail-ddt-remove"));
        if (!Number.isInteger(row)) return;
        state.dataConfig.rows = state.dataConfig.rows.filter((_, idx) => idx !== row);
        renderDataConfigTable();
      });
    });
  }

  function applyDataConfigToForm(dataConfig) {
    const normalized = dataConfig || {};
    state.dataConfig.enabled = Boolean(normalized.enabled);
    state.dataConfig.parameters = Array.isArray(normalized.parameters) ? normalized.parameters.map((item) => String(item || "")) : [];
    state.dataConfig.rows = Array.isArray(normalized.rows)
      ? normalized.rows.map((row) => (Array.isArray(row) ? row.map((item) => String(item || "")) : []))
      : [];
    els.detailDdtEnabled.checked = state.dataConfig.enabled;
    els.detailDdtParameters.value = state.dataConfig.parameters.join(", ");
    renderDataConfigTable();
  }

  function applyAssetMetaToForm(basic) {
    const source = basic || {};
    els.detailTestType.value = source.test_type || "ui";
    els.detailStatus.value = source.status || "active";
    els.detailPytestPath.value = source.pytest_path || "";
    els.detailMarkers.value = Array.isArray(source.markers) ? source.markers.join(", ") : "";
  }

  function buildDataConfigPayload() {
    refreshDataConfigFromForm();
    return {
      enabled: Boolean(state.dataConfig.enabled && state.dataConfig.parameters.length && state.dataConfig.rows.length),
      parameters: state.dataConfig.parameters,
      rows: state.dataConfig.rows
        .map((row) => row.map((item) => String(item || "").trim()))
        .filter((row) => row.some((item) => item !== "")),
    };
  }

  function buildAssetMetaPayload() {
    return {
      test_type: els.detailTestType.value || "ui",
      status: els.detailStatus.value || "active",
      pytest_path: els.detailPytestPath.value.trim(),
      markers: parseList(els.detailMarkers.value),
    };
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
      ["测试类型", basic.test_type || "ui"],
      ["标签", (basic.tags || []).join(", ") || "-"],
      ["标记", (basic.markers || []).join(", ") || "-"],
      ["创建人", basic.creator],
      ["Pytest路径", basic.pytest_path || "-"],
      ["状态", basic.status || "active"],
      ["数据驱动", basic.data_config_enabled ? "已启用" : "未启用"],
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
    applyAssetMetaToForm(basic);
    applyDataConfigToForm(payload.data_config || {});
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

  async function saveDataConfig() {
    const payload = {
      data_config: buildDataConfigPayload(),
    };
    const response = await fetch(`/api/test-cases/${caseId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      alert("保存数据驱动配置失败");
      return;
    }
    await loadDetail();
    alert("数据驱动配置已保存。");
  }

  async function saveAssetMeta() {
    const payload = buildAssetMetaPayload();
    const response = await fetch(`/api/test-cases/${caseId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      alert("保存资产属性失败");
      return;
    }
    await loadDetail();
    alert("资产属性已保存。");
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
    els.btnSaveAssetMeta.addEventListener("click", saveAssetMeta);
    els.btnAddDefect.addEventListener("click", addDefect);
    els.btnSaveDataConfig.addEventListener("click", saveDataConfig);
    els.detailDdtEnabled.addEventListener("change", refreshDataConfigFromForm);
    els.detailDdtParameters.addEventListener("change", refreshDataConfigFromForm);
    els.btnDetailDdtAddRow.addEventListener("click", () => {
      refreshDataConfigFromForm();
      if (!state.dataConfig.parameters.length) {
        alert("请先填写参数。");
        return;
      }
      state.dataConfig.rows.push(Array(state.dataConfig.parameters.length).fill(""));
      renderDataConfigTable();
    });
    els.btnDetailDdtClearRows.addEventListener("click", () => {
      state.dataConfig.rows = [];
      renderDataConfigTable();
    });
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
