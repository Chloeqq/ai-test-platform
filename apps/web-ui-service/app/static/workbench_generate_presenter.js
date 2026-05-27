(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function setText(node, value) {
    if (node) node.textContent = String(value || "");
  }

  function setHtml(node, html) {
    if (node) node.innerHTML = html;
  }

  function renderCandidateDetail(els, candidate) {
    if (!candidate) {
      if (els.candidateDetail) {
        els.candidateDetail.className = "generation-candidate-detail generation-empty";
      }
      setHtml(els.candidateDetail, "请先生成候选预览，再查看当前候选详情。");
      return;
    }
    if (els.candidateDetail) {
      els.candidateDetail.className = "generation-candidate-detail";
    }
    setHtml(
      els.candidateDetail,
      `
        <dl>
          <dt>草稿标识</dt>
          <dd>${escapeHtml(candidate.preview_id || "-")}</dd>
          <dt>标题</dt>
          <dd>${escapeHtml(candidate.title || "-")}</dd>
          <dt>页面</dt>
          <dd>${escapeHtml(candidate.page || "-")}</dd>
          <dt>类型 / 来源</dt>
          <dd>${escapeHtml(candidate.intent_type || "-")} / ${escapeHtml(candidate.source || "-")}</dd>
          <dt>优先级</dt>
          <dd>${escapeHtml(candidate.priority || "-")}</dd>
          <dt>标签</dt>
          <dd>${escapeHtml((candidate.tags || []).join(" / ") || "-")}</dd>
          <dt>步骤</dt>
          <dd><ul>${(candidate.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul></dd>
          <dt>预期结果</dt>
          <dd><ul>${(candidate.expected_results || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></dd>
        </dl>
      `
    );
  }

  function renderCandidateList(els, state, getCandidateById, onSelect) {
    if (!els.candidateList) return;
    if (!state.previewCandidates.length) {
      els.candidateList.className = "generation-candidate-list generation-empty";
      setHtml(els.candidateList, "尚未生成候选列表。");
      renderCandidateDetail(els, null);
      return;
    }
    if (!getCandidateById(state.selectedCandidateId)) {
      state.selectedCandidateId = state.previewCandidates[0].preview_id;
    }
    els.candidateList.className = "generation-candidate-list";
    setHtml(
      els.candidateList,
      state.previewCandidates
        .map(
          (candidate) => `
            <button
              type="button"
              class="generation-candidate-item ${candidate.preview_id === state.selectedCandidateId ? "is-active" : ""}"
              data-candidate-id="${escapeHtml(candidate.preview_id)}"
            >
              <strong>${escapeHtml(candidate.title)}</strong>
              <p>${escapeHtml(candidate.page || "-")} / ${escapeHtml(candidate.intent_type || "-")} / ${escapeHtml(candidate.priority || "-")}</p>
            </button>
          `
        )
        .join("")
    );
    els.candidateList.querySelectorAll("[data-candidate-id]").forEach((button) => {
      button.addEventListener("click", () => onSelect(String(button.getAttribute("data-candidate-id") || "")));
    });
    renderCandidateDetail(els, getCandidateById(state.selectedCandidateId));
  }

  window.WorkbenchGeneratePresenter = {
    renderCandidateDetail,
    renderCandidateList,
    setText,
  };
})();
