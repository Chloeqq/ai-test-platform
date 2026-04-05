(function () {
  async function downloadResponseAsFile(response, fallbackName) {
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const matched = disposition.match(/filename=([^;]+)/i);
    const filename = matched ? matched[1].replaceAll('"', "").trim() : fallbackName;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || fallbackName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function bindTableActions(config) {
    const { api, clearSelection, els, loadList, state, syncCheckAll } = config;

    els.tableBody.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement)) return;
      if (!target.classList.contains("cases-row-check")) return;
      const caseId = Number(target.getAttribute("data-case-id") || 0);
      if (!caseId) return;
      if (target.checked) state.selectedIds.add(caseId);
      else state.selectedIds.delete(caseId);
      syncCheckAll();
    });

    els.tableBody.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const actionNode = target.closest("[data-row-action]");
      if (!actionNode) return;
      const action = String(actionNode.getAttribute("data-row-action") || "").trim();
      const caseId = Number(actionNode.getAttribute("data-case-id") || 0);
      if (!caseId) return;
      if (action === "open") {
        window.location.href = "/assets/cases/" + encodeURIComponent(String(caseId));
        return;
      }
      if (action === "delete") {
        if (!window.confirm("确认删除该用例？")) return;
        api
          .batchDelete([caseId])
          .then(() => {
            clearSelection();
            return loadList();
          })
          .catch((error) => window.alert(error?.message || "删除失败"));
      }
    });

    els.btnClearSelection?.addEventListener("click", () => {
      clearSelection();
      syncCheckAll();
      els.tableBody.querySelectorAll(".cases-row-check").forEach((node) => {
        node.checked = false;
      });
    });

    els.btnArchive?.addEventListener("click", () => {
      const ids = Array.from(state.selectedIds);
      if (!ids.length) {
        window.alert("请先选择要删除的用例。");
        return;
      }
      if (!window.confirm("确认删除已选 " + ids.length + " 条用例？")) return;
      api
        .batchDelete(ids)
        .then(() => {
          clearSelection();
          return loadList();
        })
        .catch((error) => window.alert(error?.message || "批量删除失败"));
    });

    els.btnTags?.addEventListener("click", () => {
      const ids = Array.from(state.selectedIds);
      if (!ids.length) {
        window.alert("请先选择用例。");
        return;
      }
      const tags = window.prompt("请输入标签（逗号分隔）：", "");
      if (tags == null) return;
      const normalizedTags = String(tags)
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      api
        .batchTags({ ids: ids, tags: normalizedTags, mode: "replace" })
        .then(() => loadList())
        .catch((error) => window.alert(error?.message || "批量标签更新失败"));
    });

    els.btnExport?.addEventListener("click", () => {
      const ids = Array.from(state.selectedIds);
      if (!ids.length) {
        window.alert("请先选择用例。");
        return;
      }
      api
        .batchExport({ ids: ids, format: "json" })
        .then((response) => downloadResponseAsFile(response, "test-cases.json"))
        .catch((error) => window.alert(error?.message || "导出失败"));
    });
  }

  window.CasesTableActions = {
    bindTableActions: bindTableActions,
  };
})();
