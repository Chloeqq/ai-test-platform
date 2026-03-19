(function () {
  const state = {
    selectedIds: new Set(),
    page: 1,
    pageSize: 20,
    pagination: {
      page: 1,
      page_size: 20,
      total_items: 0,
      total_pages: 1,
      has_prev: false,
      has_next: false,
      prev_page: null,
      next_page: null,
    },
    treeFilter: {
      productLine: "",
      module: "",
    },
    dataConfig: {
      enabled: false,
      parameters: [],
      rows: [],
    },
  };

  let paginationInstance = null;

  const els = {
    moduleTree: document.getElementById("module-tree"),
    searchInput: document.getElementById("search-input"),
    filterTag: document.getElementById("filter-tag"),
    filterPriority: document.getElementById("filter-priority"),
    filterCreator: document.getElementById("filter-creator"),
    filterResult: document.getElementById("filter-result"),
    checkAll: document.getElementById("check-all"),
    tableBody: document.getElementById("case-table-body"),
    casePagination: document.getElementById("cases-pagination"),
    btnExport: document.getElementById("btn-export"),
    btnDelete: document.getElementById("btn-delete"),
    btnTags: document.getElementById("btn-tags"),
    btnNewCase: document.getElementById("btn-new-case"),
    newCaseDialog: document.getElementById("new-case-dialog"),
    newCaseForm: document.getElementById("new-case-form"),
    btnCloseDialog: document.getElementById("btn-close-dialog"),
    btnCancelDialog: document.getElementById("btn-cancel-dialog"),
    newMode: document.getElementById("new-mode"),
    newTestType: document.getElementById("new-test-type"),
    manualScriptWrap: document.getElementById("manual-script-wrap"),
    aiRequirementWrap: document.getElementById("ai-requirement-wrap"),
    newMarkers: document.getElementById("new-markers"),
    newPytestPath: document.getElementById("new-pytest-path"),
    newStatus: document.getElementById("new-status"),
    ddtEnabled: document.getElementById("new-ddt-enabled"),
    ddtParameters: document.getElementById("new-ddt-parameters"),
    ddtTableHead: document.getElementById("ddt-table-head"),
    ddtTableBody: document.getElementById("ddt-table-body"),
    btnDdtAddRow: document.getElementById("btn-ddt-add-row"),
    btnDdtClearRows: document.getElementById("btn-ddt-clear-rows"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function statusClass(status) {
    const normalized = String(status || "unknown").toLowerCase();
    if (normalized === "passed") return "result-passed";
    if (normalized === "failed") return "result-failed";
    if (normalized === "skipped") return "result-skipped";
    return "result-unknown";
  }

  function assetStatusClass(status) {
    const normalized = String(status || "active").toLowerCase();
    if (normalized === "active") return "asset-active";
    if (normalized === "inactive") return "asset-inactive";
    if (normalized === "deprecated") return "asset-deprecated";
    return "asset-unknown";
  }

  function getFilters() {
    return {
      q: els.searchInput.value.trim(),
      tag: els.filterTag.value,
      priority: els.filterPriority.value,
      creator: els.filterCreator.value,
      last_result: els.filterResult.value,
      product_line: state.treeFilter.productLine,
      module: state.treeFilter.module,
    };
  }

  function buildQuery(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) sp.set(key, value);
    });
    return sp.toString();
  }

  function renderPagination() {
    if (!els.casePagination) return;
    const pagination = state.pagination || {};
    const total = Number(pagination.total_items || 0);
    const page = Math.max(1, Number(pagination.page || state.page || 1));
    const pageSize = Math.max(1, Number(pagination.page_size || state.pageSize || 20));
    if (typeof window.Pagination !== "function") {
      els.casePagination.innerHTML = total
        ? `<span>第 ${page}/${Math.max(1, Number(pagination.total_pages || 1))} 页 · 共 ${total} 条</span>`
        : "<span>暂无数据</span>";
      return;
    }
    const options = {
      page,
      page_size: pageSize,
      total_items: total,
      page_size_options: [10, 20, 50, 100],
      show_total: true,
      show_quick_jumper: true,
      onChange: (nextPage, nextPageSize) => {
        loadCases(nextPage, nextPageSize);
      },
    };
    if (!paginationInstance) {
      paginationInstance = new window.Pagination("#cases-pagination", options);
      return;
    }
    paginationInstance.update(options);
  }

  async function loadTree() {
    const response = await fetch("/api/test-cases/tree");
    const payload = await response.json();
    const items = payload.items || [];
    if (!items.length) {
      els.moduleTree.innerHTML = "<p>暂无模块数据</p>";
      return;
    }
    const html = items
      .map((item) => {
        const moduleButtons = (item.modules || [])
          .map((module) => `<button data-product-line="${escapeHtml(item.product_line)}" data-module="${escapeHtml(module)}">${escapeHtml(module)}</button>`)
          .join("");
        return `
          <article class="module-item">
            <strong>${escapeHtml(item.product_line)}</strong>
            <div class="module-tags">${moduleButtons}</div>
          </article>
        `;
      })
      .join("");
    els.moduleTree.innerHTML = html;

    els.moduleTree.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        const productLine = button.getAttribute("data-product-line") || "";
        const module = button.getAttribute("data-module") || "";
        const isSame = state.treeFilter.productLine === productLine && state.treeFilter.module === module;
        state.treeFilter.productLine = isSame ? "" : productLine;
        state.treeFilter.module = isSame ? "" : module;
        loadCases(1, state.pageSize);
      });
    });
  }

  function fillSelectOptions(selectEl, values, placeholder) {
    const currentValue = selectEl.value;
    const options = [`<option value="">${placeholder}</option>`]
      .concat((values || []).map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`))
      .join("");
    selectEl.innerHTML = options;
    selectEl.value = currentValue;
  }

  function renderCaseRows(items) {
    if (!items.length) {
      els.tableBody.innerHTML = `<tr><td colspan="13">未匹配到用例</td></tr>`;
      return;
    }
    const html = items
      .map((item) => {
        const checked = state.selectedIds.has(item.id) ? "checked" : "";
        const tags = (item.tags || []).map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("");
        const markers = (item.markers || []).map((marker) => `<span class="tag-pill tag-marker">${escapeHtml(marker)}</span>`).join("");
        const ddtEnabled = item.data_config_enabled ? "enabled" : "disabled";
        const ddtLabel = item.data_config_enabled ? "已启用" : "未启用";
        return `
          <tr>
            <td><input class="case-check" type="checkbox" data-id="${item.id}" ${checked}></td>
            <td>${escapeHtml(item.name)}</td>
            <td>${escapeHtml(item.product_line)}</td>
            <td>${escapeHtml(item.module)}</td>
            <td><span class="asset-type-pill ${escapeHtml(item.test_type || "ui")}">${escapeHtml((item.test_type || "ui").toUpperCase())}</span></td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${tags || "-"}</td>
            <td>${markers || "-"}</td>
            <td><span class="ddt-indicator ${ddtEnabled}">${ddtLabel}</span></td>
            <td><span class="asset-status-pill ${assetStatusClass(item.status)}">${escapeHtml(item.status || "active")}</span></td>
            <td>${escapeHtml(item.creator)}</td>
            <td><span class="result-pill ${statusClass(item.last_execution_result)}">${escapeHtml(item.last_execution_result)}</span></td>
            <td><a href="/assets/cases/${item.id}">查看详情</a></td>
          </tr>
        `;
      })
      .join("");
    els.tableBody.innerHTML = html;

    const checkboxes = els.tableBody.querySelectorAll(".case-check");
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const id = Number(checkbox.getAttribute("data-id"));
        if (checkbox.checked) {
          state.selectedIds.add(id);
        } else {
          state.selectedIds.delete(id);
        }
        syncCheckAll(checkboxes.length);
      });
    });
    syncCheckAll(checkboxes.length);
  }

  function syncCheckAll(count) {
    if (!count) {
      els.checkAll.checked = false;
      return;
    }
    const checkedCount = Array.from(els.tableBody.querySelectorAll(".case-check:checked")).length;
    els.checkAll.checked = checkedCount === count;
  }

  async function loadCases(page = state.page, pageSize = state.pageSize) {
    const query = buildQuery({
      ...getFilters(),
      page: String(Math.max(1, Number(page) || 1)),
      page_size: String(Math.max(1, Number(pageSize) || state.pageSize || 20)),
    });
    const response = await fetch(`/api/test-cases?${query}`);
    const payload = await response.json();
    const items = payload.items || [];
    state.pagination = payload.pagination && typeof payload.pagination === "object"
      ? payload.pagination
      : {
          page: Math.max(1, Number(page) || 1),
          page_size: Math.max(1, Number(pageSize) || state.pageSize || 20),
          total_items: items.length,
          total_pages: 1,
          has_prev: false,
          has_next: false,
          prev_page: null,
          next_page: null,
        };
    state.page = Number(state.pagination.page || 1);
    state.pageSize = Number(state.pagination.page_size || pageSize || state.pageSize || 20);
    renderCaseRows(items);
    renderPagination();

    const filters = payload.filters || {};
    fillSelectOptions(els.filterTag, filters.tags || [], "标签（全部）");
    fillSelectOptions(els.filterPriority, filters.priorities || [], "优先级（全部）");
    fillSelectOptions(els.filterCreator, filters.creators || [], "创建人（全部）");
    fillSelectOptions(els.filterResult, filters.last_results || [], "最后执行结果（全部）");
  }

  function selectedIdList() {
    return Array.from(state.selectedIds.values());
  }

  async function batchExport() {
    const ids = selectedIdList();
    if (!ids.length) {
      alert("请先选择至少一条用例。");
      return;
    }
    const format = window.confirm("点击“确定”导出 CSV，点击“取消”导出 JSON。") ? "csv" : "json";
    const response = await fetch("/api/test-cases/batch/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, format }),
    });
    if (!response.ok) {
      alert("导出失败");
      return;
    }
    const blob = await response.blob();
    const filename = format === "csv" ? "test-cases.csv" : "test-cases.json";
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function batchDelete() {
    const ids = selectedIdList();
    if (!ids.length) {
      alert("请先选择至少一条用例。");
      return;
    }
    if (!window.confirm(`确定删除已选 ${ids.length} 条用例吗？`)) {
      return;
    }
    const response = await fetch("/api/test-cases/batch/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!response.ok) {
      alert("删除失败");
      return;
    }
    state.selectedIds.clear();
    await loadCases(state.page, state.pageSize);
  }

  async function batchTags() {
    const ids = selectedIdList();
    if (!ids.length) {
      alert("请先选择至少一条用例。");
      return;
    }
    const raw = window.prompt("请输入标签（逗号分隔）：", "regression,core");
    if (!raw) return;
    const tags = raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!tags.length) {
      alert("标签不能为空。");
      return;
    }
    const appendMode = window.confirm("点击“确定”追加标签，点击“取消”替换标签。");
    const response = await fetch("/api/test-cases/batch/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, tags, mode: appendMode ? "append" : "replace" }),
    });
    if (!response.ok) {
      alert("修改标签失败");
      return;
    }
    await loadCases(state.page, state.pageSize);
  }

  function toggleNewCaseMode() {
    const mode = els.newMode.value;
    const manual = mode === "manual";
    els.manualScriptWrap.classList.toggle("hidden", !manual);
    els.aiRequirementWrap.classList.toggle("hidden", manual);
  }

  function openDialog() {
    if (els.newCaseForm) {
      els.newCaseForm.reset();
    }
    resetDataConfigForm();
    toggleNewCaseMode();
    if (typeof els.newCaseDialog.showModal === "function") {
      els.newCaseDialog.showModal();
    } else {
      els.newCaseDialog.setAttribute("open", "open");
    }
  }

  function closeDialog() {
    if (typeof els.newCaseDialog.close === "function") {
      els.newCaseDialog.close();
    } else {
      els.newCaseDialog.removeAttribute("open");
    }
  }

  function parseTags(text) {
    return (text || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function parseParameters(text) {
    return parseTags(text);
  }

  function normalizeDataConfigRows(parameters, rows) {
    const width = parameters.length;
    if (!width) return [];
    return (rows || [])
      .map((row) => (row || []).map((item) => String(item || "").trim()).slice(0, width))
      .map((row) => row.concat(Array(Math.max(0, width - row.length)).fill("")))
      .filter((row) => row.some((item) => item !== ""));
  }

  function renderDataConfigTable() {
    const parameters = state.dataConfig.parameters;
    const rows = state.dataConfig.rows;

    if (!parameters.length) {
      els.ddtTableHead.innerHTML = "";
      els.ddtTableBody.innerHTML = `
        <tr>
          <td class="ddt-empty">暂无数据行。请先填写参数，再点击“添加数据行”。</td>
        </tr>
      `;
      return;
    }

    const headCells = parameters.map((item) => `<th>${escapeHtml(item)}</th>`).join("");
    els.ddtTableHead.innerHTML = `<tr>${headCells}<th class="ddt-row-action">操作</th></tr>`;

    if (!rows.length) {
      els.ddtTableBody.innerHTML = `
        <tr>
          <td class="ddt-empty" colspan="${parameters.length + 1}">暂无数据行，请点击“添加数据行”。</td>
        </tr>
      `;
      return;
    }

    els.ddtTableBody.innerHTML = rows
      .map((row, rowIndex) => {
        const cells = row
          .map(
            (value, colIndex) =>
              `<td><input type="text" data-ddt-row="${rowIndex}" data-ddt-col="${colIndex}" value="${escapeHtml(value)}"></td>`
          )
          .join("");
        return `
          <tr>
            ${cells}
            <td><button type="button" class="btn btn-danger" data-ddt-remove="${rowIndex}">删除</button></td>
          </tr>
        `;
      })
      .join("");

    els.ddtTableBody.querySelectorAll("input[data-ddt-row]").forEach((input) => {
      input.addEventListener("input", () => {
        const row = Number(input.getAttribute("data-ddt-row"));
        const col = Number(input.getAttribute("data-ddt-col"));
        if (!Number.isInteger(row) || !Number.isInteger(col)) return;
        if (!state.dataConfig.rows[row]) return;
        state.dataConfig.rows[row][col] = input.value;
      });
    });

    els.ddtTableBody.querySelectorAll("button[data-ddt-remove]").forEach((button) => {
      button.addEventListener("click", () => {
        const row = Number(button.getAttribute("data-ddt-remove"));
        if (!Number.isInteger(row)) return;
        state.dataConfig.rows = state.dataConfig.rows.filter((_, idx) => idx !== row);
        renderDataConfigTable();
      });
    });
  }

  function refreshDataConfigFromForm() {
    state.dataConfig.enabled = Boolean(els.ddtEnabled.checked);
    state.dataConfig.parameters = parseParameters(els.ddtParameters.value);
    state.dataConfig.rows = normalizeDataConfigRows(state.dataConfig.parameters, state.dataConfig.rows);
    renderDataConfigTable();
  }

  function resetDataConfigForm() {
    state.dataConfig = {
      enabled: false,
      parameters: [],
      rows: [],
    };
    els.ddtEnabled.checked = false;
    els.ddtParameters.value = "";
    renderDataConfigTable();
  }

  function addDataConfigRow() {
    refreshDataConfigFromForm();
    if (!state.dataConfig.parameters.length) {
      alert("请先填写参数（例如 username,password,expected）。");
      return;
    }
    state.dataConfig.rows.push(Array(state.dataConfig.parameters.length).fill(""));
    renderDataConfigTable();
  }

  function clearDataConfigRows() {
    state.dataConfig.rows = [];
    renderDataConfigTable();
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

  async function createCase(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const mode = form.mode.value;
    const dataConfig = buildDataConfigPayload();
    if (els.ddtEnabled.checked && (!dataConfig.parameters.length || !dataConfig.rows.length)) {
      alert("已启用数据驱动，请至少填写参数并新增一行数据。");
      return;
    }
    const payload = {
      mode,
      name: form.name.value.trim(),
      product_line: form.product_line.value.trim(),
      module: form.module.value.trim(),
      priority: form.priority.value,
      test_type: form.test_type.value,
      tags: parseTags(form.tags.value),
      markers: parseTags(form.markers.value),
      creator: form.creator.value.trim() || "admin",
      pytest_path: form.pytest_path.value.trim(),
      status: form.status.value,
      script_code: form.script_code.value,
      requirement: form.requirement.value,
      data_config: dataConfig,
    };

    const response = await fetch("/api/test-cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      alert(`创建失败：${error.detail || response.statusText}`);
      return;
    }
    closeDialog();
    form.reset();
    resetDataConfigForm();
    toggleNewCaseMode();
    await loadCases(1, state.pageSize);
  }

  function bindEvents() {
    [els.searchInput, els.filterTag, els.filterPriority, els.filterCreator, els.filterResult].forEach((item) => {
      item.addEventListener("change", () => loadCases(1, state.pageSize));
    });
    els.searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        loadCases(1, state.pageSize);
      }
    });

    els.checkAll.addEventListener("change", () => {
      const checks = els.tableBody.querySelectorAll(".case-check");
      checks.forEach((check) => {
        const id = Number(check.getAttribute("data-id"));
        check.checked = els.checkAll.checked;
        if (els.checkAll.checked) {
          state.selectedIds.add(id);
        } else {
          state.selectedIds.delete(id);
        }
      });
    });

    els.btnExport.addEventListener("click", batchExport);
    els.btnDelete.addEventListener("click", batchDelete);
    els.btnTags.addEventListener("click", batchTags);

    els.btnNewCase.addEventListener("click", openDialog);
    els.btnCloseDialog.addEventListener("click", closeDialog);
    els.btnCancelDialog.addEventListener("click", closeDialog);
    els.newMode.addEventListener("change", toggleNewCaseMode);
    els.ddtParameters.addEventListener("change", refreshDataConfigFromForm);
    els.ddtEnabled.addEventListener("change", refreshDataConfigFromForm);
    els.btnDdtAddRow.addEventListener("click", addDataConfigRow);
    els.btnDdtClearRows.addEventListener("click", clearDataConfigRows);
    els.newCaseForm.addEventListener("submit", createCase);
  }

  async function bootstrap() {
    bindEvents();
    toggleNewCaseMode();
    resetDataConfigForm();
    await loadTree();
    await loadCases();
  }

  bootstrap().catch((error) => {
    console.error(error);
    alert("加载用例库失败，请检查后端服务日志。");
  });
})();
