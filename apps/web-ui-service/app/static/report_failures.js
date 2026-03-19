(function () {
  const shell = document.getElementById("report-failures-shell");
  if (!shell) return;

  const els = {
    filterCase: document.getElementById("rp-filter-case"),
    filterKeyword: document.getElementById("rp-filter-keyword"),
    filterDefect: document.getElementById("rp-filter-defect"),
    filterBtn: document.getElementById("rp-filter-search"),
    list: document.getElementById("rp-failure-list"),
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

  function renderDefects(defects) {
    if (!defects || !defects.length) return "未关联";
    return defects
      .map((defect) => {
        const id = escapeHtml(defect.defect_id || "-");
        const url = defect.defect_url ? escapeHtml(defect.defect_url) : "";
        if (!url) return id;
        return `<a href="${url}" target="_blank" rel="noreferrer">${id}</a>`;
      })
      .join("、");
  }

  function renderItem(item) {
    return `
      <li class="failure-item" data-case-id="${escapeHtml(item.case_id || "")}">
        <div class="failure-title">${escapeHtml(item.case_id || "-")} · ${escapeHtml(item.case_title || "-")}</div>
        <div class="failure-meta">
          <span>风险：${escapeHtml(item.risk_level || "-")}</span>
          <span>分类：${escapeHtml(item.failure_category || "-")}</span>
          <span>置信度：${escapeHtml(item.confidence || "-")}</span>
          <span>完成时间：${escapeHtml(formatTime(item.finished_at))}</span>
        </div>
        <div class="failure-meta">
          <span>摘要：${escapeHtml(item.summary || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>原因：${escapeHtml(item.likely_cause || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>建议：${escapeHtml(item.recommended_action || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>缺陷：${renderDefects(item.defects)}</span>
        </div>
        <div class="failure-meta">
          <span>证据目录：<code>${escapeHtml(item.artifact_dir || "-")}</code></span>
        </div>
        <div class="failure-actions">
          <button class="btn btn-primary" data-action="link-defect" data-case-id="${escapeHtml(item.case_id || "")}">关联缺陷</button>
          <button class="btn" data-action="copy-path" data-path="${escapeHtml(item.artifact_dir || "")}">复制证据目录</button>
        </div>
      </li>
    `;
  }

  async function loadFailures() {
    const params = new URLSearchParams();
    if (els.filterCase.value.trim()) {
      params.set("case_id", els.filterCase.value.trim());
    }
    if (els.filterKeyword.value.trim()) {
      params.set("keyword", els.filterKeyword.value.trim());
    }
    params.set("defect_status", els.filterDefect.value || "all");
    const resp = await fetch(`/api/report/failures?${params.toString()}`);
    if (!resp.ok) {
      els.list.innerHTML = "<li>加载失败</li>";
      return;
    }
    const data = await resp.json();
    const items = data.items || [];
    if (!items.length) {
      els.list.innerHTML = "<li>暂无失败记录</li>";
      return;
    }
    els.list.innerHTML = items.map(renderItem).join("");
  }

  async function linkDefect(caseId) {
    if (!caseId) return;
    const defectId = window.prompt("请输入缺陷单号");
    if (!defectId) return;
    const defectUrl = window.prompt("可选：缺陷链接（可留空）") || "";
    const resp = await fetch("/api/defects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        defect_id: defectId.trim(),
        defect_url: defectUrl.trim(),
        system: "manual",
        note: "",
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`关联失败：${error.detail || resp.statusText}`);
      return;
    }
    alert("关联成功。");
    loadFailures();
  }

  function copyPath(path) {
    if (!path) {
      alert("暂无证据目录。");
      return;
    }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(path)
        .then(() => alert("已复制到剪贴板。"))
        .catch(() => alert("复制失败，请手动复制。"));
    } else {
      alert(`证据目录：${path}`);
    }
  }

  function bindEvents() {
    els.filterBtn.addEventListener("click", loadFailures);
    els.list.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const action = target.getAttribute("data-action");
      if (action === "link-defect") {
        linkDefect(target.getAttribute("data-case-id") || "");
      }
      if (action === "copy-path") {
        copyPath(target.getAttribute("data-path") || "");
      }
    });
  }

  function bootstrap() {
    bindEvents();
    loadFailures().catch((error) => {
      console.error(error);
      els.list.innerHTML = "<li>加载失败</li>";
    });
  }

  bootstrap();
})();
