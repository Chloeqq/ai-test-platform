(function () {
  const shared = window.qualityClustersShared;
  if (!shared) return;

  function createQualityClustersDetailController(options) {
    const { els, state } = options;

    function clusterAttributionText(cluster) {
      if (Number(cluster.requires_manual_review_count || 0) > 0) {
        return "优先回看人工复核样本和失败来源，再决定是否直接建缺陷。";
      }
      if (shared.severityRank(cluster.severity) <= 2) {
        return "这是高优先级聚类，建议先补缺陷闭环并联动执行结果页。";
      }
      return "先观察重复出现的范围，再决定是否升级为治理任务。";
    }

    function renderSamples(sampleCases) {
      const rows = Array.isArray(sampleCases) ? sampleCases : [];
      if (!rows.length) return '<li class="empty-state">当前聚类暂无样本用例。</li>';
      return rows
        .slice(0, 5)
        .map(
          (item) => `
            <li class="cluster-sample-item">
              <div class="cluster-card-head">
                <strong>${shared.escapeHtml(shared.displayCaseId(item.case_id || "-"))}</strong>
                <span>${shared.escapeHtml(shared.formatTime(item.started_at || item.last_seen_at))}</span>
              </div>
              <div class="cluster-card-meta">
                <span>状态 ${shared.escapeHtml(item.status || "-")}</span>
                <span>风险 ${shared.escapeHtml(item.risk_level || "-")}</span>
                <span>队列 ${shared.escapeHtml(item.queue || "-")}</span>
              </div>
            </li>
          `
        )
        .join("");
    }

    async function createDefectForCurrentCluster() {
      const cluster = state.currentCluster;
      if (!cluster || typeof cluster !== "object") {
        window.alert("请先选择一个聚类。");
        return;
      }
      const caseId = String(cluster.latest_case_id || "").trim();
      if (!caseId) {
        window.alert("当前聚类没有可关联的最新用例，暂时无法创建缺陷。");
        return;
      }
      const defectId = String(window.prompt("请输入缺陷单号（如 BUG-5201）：", "") || "").trim();
      if (!defectId) return;
      const defectUrl = String(window.prompt("可选：缺陷链接（可留空）：", "") || "").trim();
      const response = await fetch("/api/defects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          defect_id: defectId,
          defect_url: defectUrl,
          system: "failure-cluster",
          note: [
            `cluster_id=${cluster.cluster_id || "-"}`,
            `failure_class=${cluster.failure_class || "-"}`,
            `queue=${cluster.queue || "-"}`,
            `severity=${cluster.severity || "-"}`,
            `occurrence_count=${cluster.occurrence_count || 0}`,
          ].join("; "),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        window.alert(`创建缺陷失败：${payload.detail || response.statusText}`);
        return;
      }
      window.alert("缺陷关联成功。");
    }

    function renderDetail(cluster) {
      if (!cluster || typeof cluster !== "object") {
        state.currentCluster = null;
        els.detailPanel.innerHTML = '<div class="empty-state">先选择一个失败聚类。</div>';
        return;
      }
      state.currentCluster = cluster;
      const clusterId = String(cluster.cluster_id || "").trim();
      const latestCaseId = String(cluster.latest_case_id || "").trim();
      const openCaseHref = latestCaseId ? `/report/failures?case_id=${encodeURIComponent(latestCaseId)}` : "/execution/results/failures";
      els.detailPanel.innerHTML = `
        <section class="detail-highlight">
          <h3>${shared.escapeHtml(cluster.failure_class || clusterId || "-")}</h3>
          <p>${shared.escapeHtml(clusterAttributionText(cluster))}</p>
        </section>
        <div class="cluster-pill-list">
          <article class="cluster-pill"><span>聚类 ID</span><strong>${shared.escapeHtml(clusterId || "-")}</strong></article>
          <article class="cluster-pill"><span>队列</span><strong>${shared.escapeHtml(cluster.queue || "-")}</strong></article>
          <article class="cluster-pill"><span>严重级别</span><strong>${shared.escapeHtml(cluster.severity || "-")}</strong></article>
          <article class="cluster-pill"><span>人工复核占比</span><strong>${shared.escapeHtml(`${Math.round(Number(cluster.manual_review_ratio || 0) * 100)}%`)}</strong><p>${shared.escapeHtml(`${cluster.requires_manual_review_count || 0}/${cluster.occurrence_count || 0}`)}</p></article>
          <article class="cluster-pill"><span>首次出现</span><strong>${shared.escapeHtml(shared.formatTime(cluster.first_seen_at))}</strong></article>
          <article class="cluster-pill"><span>最后出现</span><strong>${shared.escapeHtml(shared.formatTime(cluster.last_seen_at))}</strong></article>
        </div>
        <div class="kv-list">
          <article class="kv-item"><span>Bucket Key</span><p>${shared.escapeHtml(cluster.bucket_key || "-")}</p></article>
          <article class="kv-item"><span>责任团队</span><p>${shared.escapeHtml(cluster.owner_team || "-")}</p></article>
          <article class="kv-item"><span>最新用例</span><p>${shared.escapeHtml(shared.displayCaseId(latestCaseId || "-"))}</p></article>
          <article class="kv-item"><span>治理建议</span><p>${shared.escapeHtml(clusterAttributionText(cluster))}</p></article>
        </div>
        <section class="cluster-alert-section">
          <div class="cluster-section-head">
            <h3>最近样本</h3>
            <p>优先从最近失败样本确认错误共性和实际影响范围。</p>
          </div>
          <ul class="cluster-sample-list">${renderSamples(cluster.sample_cases)}</ul>
        </section>
        <div class="cluster-detail-actions">
          <button id="create-defect-btn" class="btn btn-primary" type="button">一键创建缺陷</button>
          <a class="action-link" href="${openCaseHref}" target="_blank" rel="noreferrer">打开最新用例</a>
        </div>
      `;

      const createDefectBtn = document.getElementById("create-defect-btn");
      createDefectBtn?.addEventListener("click", () => {
        createDefectForCurrentCluster().catch((error) => {
          console.error(error);
          window.alert("创建缺陷失败，请稍后重试。");
        });
      });
    }

    async function loadClusterDetail(clusterId) {
      if (!clusterId) {
        renderDetail(null);
        return;
      }
      els.detailPanel.innerHTML = '<div class="loading-state">正在加载聚类详情...</div>';
      const limit = Number(els.limitSelect?.value || 200) || 200;
      const response = await fetch(`/failures/clusters/${encodeURIComponent(clusterId)}?limit=${encodeURIComponent(limit)}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("聚类详情加载失败");
      const payload = await response.json();
      renderDetail(payload.cluster || null);
    }

    return {
      loadClusterDetail,
      renderDetail,
    };
  }

  window.createQualityClustersDetailController = createQualityClustersDetailController;
})();
