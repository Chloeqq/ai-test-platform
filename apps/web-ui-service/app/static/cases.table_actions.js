(function () {
  function bindTableActions(options) {
    const {
      api,
      clearSelection,
      els,
      loadList,
      renderTable,
      state,
      syncCheckAll,
    } = options;

    function ensureSelection() {
      const ids = Array.from(state.selectedIds.values());
      if (ids.length) return ids;
      window.alert("请先选择至少一条用例。");
      return null;
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
      if (action === "tag") {
        const nextTags = window.prompt("请输入新的标签，使用逗号分隔", "smoke,regression") || "";
        api.updateTags([caseId], nextTags.split(",").map((item) => item.trim()).filter(Boolean))
          .then(() => loadList())
          .catch((error) => window.alert(error.message || "标签更新失败"));
        return;
      }
      if (action === "archive") {
        if (!window.confirm("确认将该用例标记为废弃状态吗？该操作不会物理删除。")) return;
        api.updateStatus([caseId], "deprecated")
          .then(() => loadList())
          .catch((error) => window.alert(error.message || "废弃失败"));
      }
    });

    els.btnExport.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      api.export(ids).then(() => window.alert("已导出选中用例")).catch((error) => window.alert(error.message || "导出失败"));
    });

    els.btnArchive.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      if (!window.confirm(`确认将选中的 ${ids.length} 条用例标记为废弃状态吗？该操作不会物理删除。`)) return;
      api.updateStatus(ids, "deprecated").then(() => loadList()).catch((error) => window.alert(error.message || "废弃失败"));
    });

    els.btnTags.addEventListener("click", () => {
      const ids = ensureSelection();
      if (!ids) return;
      const nextTags = window.prompt("请输入新的标签，使用逗号分隔", "smoke,regression") || "";
      api.updateTags(ids, nextTags.split(",").map((item) => item.trim()).filter(Boolean)).then(() => loadList()).catch((error) => window.alert(error.message || "标签更新失败"));
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
