(function () {
  const shell = document.getElementById("report-failures-shell");
  if (!shell) return;

  const els = {
    filterCase: document.getElementById("rp-filter-case"),
    filterKeyword: document.getElementById("rp-filter-keyword"),
    filterDefect: document.getElementById("rp-filter-defect"),
    filterBtn: document.getElementById("rp-filter-search"),
    evidenceMeta: document.getElementById("rp-evidence-meta"),
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
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
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

  function normalizeEvidenceSource(value) {
    const source = String(value || "").trim().toLowerCase();
    if (source === "manifest") {
      return { label: "manifest 主路径", className: "evidence-source-manifest" };
    }
    if (source === "compat_scan") {
      return { label: "兼容扫描回退", className: "evidence-source-compat" };
    }
    return { label: "未知来源", className: "evidence-source-unknown" };
  }

  function renderSourceEvidence(items) {
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      return "-";
    }
    return rows
      .slice(0, 3)
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const signal = String(item.signal || "-").trim();
        const value = String(item.value || "-").trim();
        const origin = String(item.origin || "-").trim();
        return `${signal}:${value} @ ${origin}`;
      })
      .filter(Boolean)
      .join("；");
  }

  function renderItem(item) {
    const source = normalizeEvidenceSource(item.evidence_source);
    const manifestPath = String(item.manifest_path || "").trim();
    return `
      <li class="failure-item" data-case-id="${escapeHtml(item.case_id || "")}">
        <div class="failure-title">${escapeHtml(displayCaseId(item.case_id || "-"))} · ${escapeHtml(item.case_title || "-")}</div>
        <div class="failure-meta">
          <span>风险：${escapeHtml(item.risk_level || "-")}</span>
          <span>分类：${escapeHtml(item.failure_category || "-")}</span>
          <span>来源：${escapeHtml(item.failure_source || "-")}</span>
          <span>置信度：${escapeHtml(item.confidence || "-")}</span>
          <span>人工复核：${escapeHtml(item.requires_manual_review ? "是" : "否")}</span>
          <span>完成时间：${escapeHtml(formatTime(item.finished_at))}</span>
        </div>
        <div class="failure-meta">
          <span>摘要：${escapeHtml(item.summary || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>原因：${escapeHtml(item.likely_cause || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>来源依据：${escapeHtml(item.failure_source_reason || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>来源证据：${escapeHtml(renderSourceEvidence(item.source_evidence))}</span>
        </div>
        <div class="failure-meta">
          <span>建议：${escapeHtml(item.recommended_action || "-")}</span>
        </div>
        <div class="failure-meta">
          <span>缺陷：${renderDefects(item.defects)}</span>
        </div>
        <div class="failure-meta">
          <span>证据来源：<span class="evidence-source-tag ${source.className}">${escapeHtml(source.label)}</span></span>
          ${manifestPath ? `<span>Manifest：<code>${escapeHtml(manifestPath)}</code></span>` : ""}
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

  function renderEvidenceMeta(meta) {
    if (!els.evidenceMeta) return;
    const info = meta && typeof meta === "object" ? meta : {};
    const manifestCount = Number(info.manifest_entry_count || 0);
    const compatCount = Number(info.compat_scan_entry_count || 0);
    const compatEnabled = Boolean(info.compat_scan_enabled);
    const policyMode = String(info.policy_mode || (compatEnabled ? "compat" : "strict"));
    const health = String(info.health || "unknown");
    const manifestFirstRatio = Number(info.manifest_first_ratio || 0);
    const fallbackRatio = Number(info.fallback_ratio || 0);
    const skipped = Number(info.compat_scan_skipped_count || 0);
    const invalidManifest = Number(info.invalid_manifest_count || 0);
    const missingManifest = Number(info.missing_manifest_count || 0);
    const warning = compatCount > 0 || skipped > 0 || invalidManifest > 0 || health !== "healthy";
    const status = compatEnabled ? "兼容回退开启" : "兼容回退关闭";
    const warnings = Array.isArray(info.warnings) ? info.warnings.slice(0, 3).map((item) => String(item || "").trim()).filter(Boolean) : [];
    const details = [
      `policy=${policyMode}`,
      `health=${health}`,
      `manifest=${manifestCount}`,
      `compat=${compatCount}`,
      `manifest_ratio=${Math.round(manifestFirstRatio * 100)}%`,
      `fallback_ratio=${Math.round(fallbackRatio * 100)}%`,
      `missing_manifest=${missingManifest}`,
      `invalid_manifest=${invalidManifest}`,
      `skipped=${skipped}`,
    ].join("，");
    const warningText = warnings.length ? `<br>告警：${warnings.map((item) => escapeHtml(item)).join(" / ")}` : "";
    els.evidenceMeta.innerHTML = `证据读取状态：${escapeHtml(status)}（${escapeHtml(details)}）${warningText}`;
    els.evidenceMeta.hidden = false;
    els.evidenceMeta.classList.toggle("warning", warning);
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
    const resp = await fetch(`/api/report/failures?${params.toString()}`, { cache: "no-store" });
    if (!resp.ok) {
      els.list.innerHTML = "<li>加载失败</li>";
      return;
    }
    const data = await resp.json();
    renderEvidenceMeta(data.evidence_meta);
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
      cache: "no-store",
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
