(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function setText(node, text) {
    if (!node) return;
    node.textContent = String(text || "");
  }

  function renderCandidateList(els, state, getCandidateById, onSelect) {
    if (!els?.candidateList) return;
    const rows = Array.isArray(state?.previewCandidates) ? state.previewCandidates : [];
    if (!rows.length) {
      els.candidateList.className = "generation-candidate-list generation-empty";
      els.candidateList.textContent = "尚未生成候选列表。";
      if (els.candidateDetail) {
        els.candidateDetail.className = "generation-candidate-detail generation-empty";
        els.candidateDetail.textContent = "请先生成候选预览，再查看当前候选详情。";
      }
      return;
    }
    els.candidateList.className = "generation-candidate-list";
    els.candidateList.innerHTML = rows
      .map((item) => {
        const active = item.preview_id === state.selectedCandidateId ? " is-active" : "";
        return (
          '<button type="button" class="generation-candidate-item' +
          active +
          '" data-preview-id="' +
          escapeHtml(item.preview_id) +
          '">' +
          "<strong>" +
          escapeHtml(item.title || "候选 Draft") +
          "</strong>" +
          "<p>" +
          escapeHtml(item.summary || "暂无摘要") +
          "</p>" +
          "</button>"
        );
      })
      .join("");

    els.candidateList.querySelectorAll("[data-preview-id]").forEach((button) => {
      button.addEventListener("click", () => {
        const previewId = String(button.getAttribute("data-preview-id") || "").trim();
        if (!previewId) return;
        if (typeof onSelect === "function") onSelect(previewId);
      });
    });

    const selected = getCandidateById ? getCandidateById(state.selectedCandidateId) : rows[0];
    renderCandidateDetail(els, selected || rows[0]);
  }

  function renderCandidateDetail(els, candidate) {
    if (!els?.candidateDetail) return;
    if (!candidate || typeof candidate !== "object") {
      els.candidateDetail.className = "generation-candidate-detail generation-empty";
      els.candidateDetail.textContent = "当前没有候选详情。";
      return;
    }
    const points = Array.isArray(candidate.test_points) ? candidate.test_points : [];
    const tags = Array.isArray(candidate.tags) ? candidate.tags : [];
    els.candidateDetail.className = "generation-candidate-detail";
    els.candidateDetail.innerHTML =
      "<dl>" +
      "<dt>候选 ID</dt><dd>" +
      escapeHtml(candidate.preview_id) +
      "</dd>" +
      "<dt>页面</dt><dd>" +
      escapeHtml(candidate.page || "-") +
      "</dd>" +
      "<dt>优先级</dt><dd>" +
      escapeHtml(candidate.priority || "-") +
      "</dd>" +
      "<dt>标签</dt><dd>" +
      escapeHtml(tags.join(", ") || "-") +
      "</dd>" +
      "</dl>" +
      "<ul>" +
      points.slice(0, 10).map((item) => "<li>" + escapeHtml(item) + "</li>").join("") +
      (points.length > 10 ? "<li>... 共 " + points.length + " 条测试点</li>" : "") +
      "</ul>";
  }

  window.WorkbenchGeneratePresenter = {
    renderCandidateDetail: renderCandidateDetail,
    renderCandidateList: renderCandidateList,
    setText: setText,
  };
})();
