(function () {
  function triggerDownload(file) {
    const blob = file && file.blob;
    if (!(blob instanceof Blob)) {
      throw new Error("导出文件生成失败");
    }
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = file.filename || "test-cases-template.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 1000);
  }

  function bindTableActions(options) {
    const {
      api,
      clearSelection,
      els,
      getCaseItemById,
      hasBlockedSelection,
      isCaseWriteBlocked,
      loadList,
      renderTable,
      reviewMode,
      state,
      syncCheckAll,
    } = options;

    function ensureSelection() {
      const ids = Array.from(state.selectedIds.values());
      if (ids.length) return ids;
      window.alert("请先选择至少一条用例。");
      return null;
    }

    function selectedCaseIds() {
      const selectedIdSet = state.selectedIds instanceof Set ? state.selectedIds : new Set();
      return (Array.isArray(state.items) ? state.items : [])
        .filter((item) => selectedIdSet.has(item.id))
        .map((item) => String(item.case_id || "").trim())
        .filter(Boolean);
    }

    function resolveCaseBusinessId(numericId) {
      const target = (Array.isArray(state.items) ? state.items : []).find((item) => Number(item.id || 0) === Number(numericId || 0));
      return String(target && target.case_id || "").trim();
    }

    function ensureRowWriteAllowed(caseId) {
      const target = typeof getCaseItemById === "function" ? getCaseItemById(caseId) : null;
      if (typeof isCaseWriteBlocked === "function" && isCaseWriteBlocked(target)) {
        window.alert("当前用例所属项目为 inactive，仅允许浏览、运行、导出和删除；编辑类操作已禁用。");
        return false;
      }
      return true;
    }

    function ensureSelectionWriteAllowed() {
      if (typeof hasBlockedSelection === "function" && hasBlockedSelection()) {
        window.alert("当前选择中包含 inactive 项目的用例，仅允许运行、导出和删除；批量编辑类操作已禁用。");
        return false;
      }
      return true;
    }

    function redirectToList(caseId) {
      const params = new URLSearchParams();
      if (caseId) params.set("q", caseId);
      window.location.href = params.toString() ? `/cases?${params.toString()}` : "/cases";
    }

    els.tableBody.addEventListener("change", (event) => {
      const checkbox = event.target instanceof HTMLInputElement && event.target.classList.contains("case-check") ? event.target : null;
      if (!checkbox) return;
      const id = Number(checkbox.dataset.id || 0);
      if (!id) return;
      if (checkbox.checked) state.selectedIds.add(id);
      else state.selectedIds.delete(id);
      syncCheckAll();
    });

    els.tableBody.addEventListener("click", (event) => {
      const actionButton = event.target instanceof Element ? event.target.closest("[data-row-action]") : null;
      if (!actionButton) return;
      const caseId = Number(actionButton.getAttribute("data-case-id") || 0);
      if (!caseId) return;
      const action = actionButton.getAttribute("data-row-action");
      if (action === "run") {
        const businessCaseId = resolveCaseBusinessId(caseId);
        if (!businessCaseId) {
          window.alert("当前用例缺少 case_id，无法执行。");
          return;
        }
        const params = new URLSearchParams();
        params.set("case_ids", businessCaseId);
        window.location.href = `/execution/runs?${params.toString()}`;
        return;
      }
      if (action === "approve") {
        if (!ensureRowWriteAllowed(caseId)) return;
        api.updateStatus([caseId], "active")
          .then(() => {
            window.alert("审核通过，已更新为启用状态。");
            if (reviewMode) {
              redirectToList(resolveCaseBusinessId(caseId));
              return null;
            }
            return loadList();
          })
          .catch((error) => window.alert(error.message || "审核通过失败"));
        return;
      }
      if (action === "reject") {
        if (!ensureRowWriteAllowed(caseId)) return;
        api.updateStatus([caseId], "deprecated")
          .then(() => {
            window.alert("已驳回，状态更新为已废弃。");
            if (reviewMode) {
              redirectToList(resolveCaseBusinessId(caseId));
              return null;
            }
            return loadList();
          })
          .catch((error) => window.alert(error.message || "驳回失败"));
        return;
      }
      if (action === "delete") {
        if (!window.confirm("确认删除该待审核用例吗？该操作不可恢复。")) return;
        const businessCaseId = resolveCaseBusinessId(caseId);
        api.batchDelete([caseId], businessCaseId ? [businessCaseId] : [])
          .then(() => {
            window.alert("删除成功。");
            if (reviewMode) {
              redirectToList("");
              return null;
            }
            return loadList();
          })
          .catch((error) => window.alert(error.message || "删除失败"));
        return;
      }
      if (action === "tag") {
        if (!ensureRowWriteAllowed(caseId)) return;
        const nextTags = window.prompt("请输入新的标签，使用逗号分隔", "smoke,regression") || "";
        api.updateTags([caseId], nextTags.split(",").map((item) => item.trim()).filter(Boolean))
          .then(() => loadList())
          .catch((error) => window.alert(error.message || "标签更新失败"));
        return;
      }
      if (action === "archive") {
        if (!ensureRowWriteAllowed(caseId)) return;
        if (!window.confirm("确认将该用例标记为废弃状态吗？该操作不会物理删除。")) return;
        api.updateStatus([caseId], "deprecated")
          .then(() => loadList())
          .catch((error) => window.alert(error.message || "废弃失败"));
      }
    });

    els.btnExport.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      api.export(ids, "xlsx")
        .then((file) => {
          triggerDownload(file);
          window.alert("已按模板导出 Excel。");
        })
        .catch((error) => window.alert(error.message || "导出失败"));
    });

    els.btnArchive.addEventListener("click", () => {
      if (!ensureSelectionWriteAllowed()) return;
      const ids = ensureSelection();
      if (!ids) return;
      if (!window.confirm(`确认将选中的 ${ids.length} 条用例标记为废弃状态吗？该操作不会物理删除。`)) return;
      api.updateStatus(ids, "deprecated").then(() => loadList()).catch((error) => window.alert(error.message || "废弃失败"));
    });

    els.btnTags.addEventListener("click", () => {
      if (!ensureSelectionWriteAllowed()) return;
      const ids = ensureSelection();
      if (!ids) return;
      const nextTags = window.prompt("请输入新的标签，使用逗号分隔", "smoke,regression") || "";
      api.updateTags(ids, nextTags.split(",").map((item) => item.trim()).filter(Boolean)).then(() => loadList()).catch((error) => window.alert(error.message || "标签更新失败"));
    });

    els.btnBatchDelete.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      if (!window.confirm(`确认删除选中的 ${ids.length} 条用例吗？该操作不可恢复。`)) return;
      const caseIds = selectedCaseIds();
      api.batchDelete(ids, caseIds)
        .then(() => {
          window.alert("批量删除成功。");
          return loadList();
        })
        .catch((error) => window.alert(error.message || "批量删除失败"));
    });

    els.btnBatchRun.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      const caseIds = selectedCaseIds();
      if (!caseIds.length) {
        window.alert("当前选择缺少有效 case_id，无法发起批量运行。");
        return;
      }
      const params = new URLSearchParams();
      params.set("case_ids", caseIds.join(","));
      window.location.href = `/execution/runs?${params.toString()}`;
    });

    els.btnClearSelection.addEventListener("click", () => {
      clearSelection();
      renderTable();
    });
  }

  window.CasesTableActions = {
    bindTableActions,
  };
})();
