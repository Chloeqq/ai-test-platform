(function () {
  const state = {
    selectedIds: new Set(),
    treeFilter: {
      productLine: "",
      module: "",
    },
  };

  const els = {
    moduleTree: document.getElementById("module-tree"),
    searchInput: document.getElementById("search-input"),
    filterTag: document.getElementById("filter-tag"),
    filterPriority: document.getElementById("filter-priority"),
    filterCreator: document.getElementById("filter-creator"),
    filterResult: document.getElementById("filter-result"),
    checkAll: document.getElementById("check-all"),
    tableBody: document.getElementById("case-table-body"),
    btnExport: document.getElementById("btn-export"),
    btnDelete: document.getElementById("btn-delete"),
    btnTags: document.getElementById("btn-tags"),
    btnNewCase: document.getElementById("btn-new-case"),
    newCaseDialog: document.getElementById("new-case-dialog"),
    newCaseForm: document.getElementById("new-case-form"),
    btnCloseDialog: document.getElementById("btn-close-dialog"),
    btnCancelDialog: document.getElementById("btn-cancel-dialog"),
    newMode: document.getElementById("new-mode"),
    manualScriptWrap: document.getElementById("manual-script-wrap"),
    aiRequirementWrap: document.getElementById("ai-requirement-wrap"),
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
        loadCases();
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
      els.tableBody.innerHTML = `<tr><td colspan="9">未匹配到用例</td></tr>`;
      return;
    }
    const html = items
      .map((item) => {
        const checked = state.selectedIds.has(item.id) ? "checked" : "";
        const tags = (item.tags || []).map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("");
        return `
          <tr>
            <td><input class="case-check" type="checkbox" data-id="${item.id}" ${checked}></td>
            <td>${escapeHtml(item.name)}</td>
            <td>${escapeHtml(item.product_line)}</td>
            <td>${escapeHtml(item.module)}</td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${tags || "-"}</td>
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

  async function loadCases() {
    const query = buildQuery(getFilters());
    const response = await fetch(`/api/test-cases?${query}`);
    const payload = await response.json();
    const items = payload.items || [];
    renderCaseRows(items);

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
    await loadCases();
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
    await loadCases();
  }

  function toggleNewCaseMode() {
    const mode = els.newMode.value;
    const manual = mode === "manual";
    els.manualScriptWrap.classList.toggle("hidden", !manual);
    els.aiRequirementWrap.classList.toggle("hidden", manual);
  }

  function openDialog() {
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

  async function createCase(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const mode = form.mode.value;
    const payload = {
      mode,
      name: form.name.value.trim(),
      product_line: form.product_line.value.trim(),
      module: form.module.value.trim(),
      priority: form.priority.value,
      tags: parseTags(form.tags.value),
      creator: form.creator.value.trim() || "admin",
      script_code: form.script_code.value,
      requirement: form.requirement.value,
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
    toggleNewCaseMode();
    await loadCases();
  }

  function bindEvents() {
    [els.searchInput, els.filterTag, els.filterPriority, els.filterCreator, els.filterResult].forEach((item) => {
      item.addEventListener("change", loadCases);
    });
    els.searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        loadCases();
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
    els.newCaseForm.addEventListener("submit", createCase);
  }

  async function bootstrap() {
    bindEvents();
    toggleNewCaseMode();
    await loadTree();
    await loadCases();
  }

  bootstrap().catch((error) => {
    console.error(error);
    alert("加载用例库失败，请检查后端服务日志。");
  });
})();
