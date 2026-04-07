(function () {
  const shell = document.getElementById("report-allure-shell");
  if (!shell) return;

  const els = {
    status: document.getElementById("rp-allure-status"),
    frame: document.getElementById("rp-allure-frame"),
    refresh: document.getElementById("rp-allure-refresh"),
    open: document.getElementById("rp-allure-open"),
  };

  function buildAllureUrl(base, version, nonce) {
    const v = Number(version) || Date.now();
    const n = Number(nonce) || Date.now();
    const sep = String(base || "/allure/index.html").includes("?") ? "&" : "?";
    return `${base || "/allure/index.html"}${sep}v=${v}&nonce=${n}`;
  }

  function formatSummary(summary) {
    const stat = (summary && summary.statistic) || {};
    const time = (summary && summary.time) || {};
    const total = Number(stat.total || 0);
    const passed = Number(stat.passed || 0);
    const failed = Number(stat.failed || 0);
    const broken = Number(stat.broken || 0);
    const start = Number(time.start || 0);
    const stop = Number(time.stop || 0);
    const dateText = start > 0 && stop > 0
      ? (typeof window.platformFormatDateRange === "function"
        ? window.platformFormatDateRange(start, stop, "时间未知")
        : "时间未知")
      : "时间未知";
    return `总数:${total} 通过:${passed} 失败:${failed} 异常:${broken} 时间:${dateText}`;
  }

  function formatSnapshotVersion(version) {
    const text = String(version || "").trim();
    if (!text || text === "0") return "";
    if (typeof window.platformFormatDateTime === "function") {
      const formatted = window.platformFormatDateTime(version, "");
      if (formatted && formatted !== text) {
        return `快照:${formatted}`;
      }
    }
    if (text.length > 12) {
      return `版本:${text.slice(0, 8)}...`;
    }
    return `版本:${text}`;
  }

  function buildStatusMessage(prefix, data) {
    const summaryText = formatSummary((data && data.summary) || {});
    const snapshotText = formatSnapshotVersion(data && data.version);
    return snapshotText ? `${prefix}。${summaryText} ${snapshotText}` : `${prefix}。${summaryText}`;
  }

  function applyFrame(allureIndex, version) {
    const url = buildAllureUrl(allureIndex || "/allure/index.html", version, Date.now());
    els.frame.style.display = "block";
    els.frame.setAttribute("src", "about:blank");
    setTimeout(() => {
      els.frame.setAttribute("src", url);
      if (els.open) {
        els.open.setAttribute("href", url);
      }
    }, 40);
  }

  async function clearBrowserCaches() {
    try {
      if ("caches" in window && caches.keys) {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      }
    } catch (error) {
      console.warn("clear caches failed", error);
    }
    try {
      if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((reg) => reg.unregister()));
      }
    } catch (error) {
      console.warn("clear service worker failed", error);
    }
  }

  async function loadAllure() {
    const resp = await fetch("/api/report/allure", { cache: "no-store" });
    if (!resp.ok) {
      els.status.textContent = "加载失败，请检查服务状态。";
      els.frame.style.display = "none";
      return;
    }
    const data = await resp.json();
    if (data.available) {
      els.status.textContent = buildStatusMessage("Allure 报告已就绪", data);
      applyFrame(data.allure_index, data.version);
    } else {
      els.status.textContent = "暂未生成 Allure 报告，请先执行用例。";
      els.frame.style.display = "none";
    }
  }

  async function refreshAllure() {
    if (!els.refresh) return;
    els.refresh.disabled = true;
    els.status.textContent = "正在刷新 Allure 报告...";
    try {
      await clearBrowserCaches();
      const resp = await fetch("/api/report/allure/refresh", {
        method: "POST",
        cache: "no-store",
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        const detail = error.detail || {};
        const message = detail.message || "刷新失败，请稍后重试。";
        const stderr = detail.stderr || "";
        els.status.textContent = stderr ? `${message} ${stderr}` : message;
        return;
      }
      const data = await resp.json();
      if (data.available) {
        els.status.textContent = buildStatusMessage("Allure 报告已刷新", data);
        applyFrame(data.allure_index || "/allure/index.html", data.version);
      } else {
        els.status.textContent = "刷新完成，但报告仍不可用。";
        els.frame.style.display = "none";
      }
    } catch (error) {
      console.error(error);
      els.status.textContent = "刷新失败，请检查后端服务。";
    } finally {
      els.refresh.disabled = false;
    }
  }

  if (els.refresh) {
    els.refresh.addEventListener("click", refreshAllure);
  }

  loadAllure().catch((error) => {
    console.error(error);
    els.status.textContent = "加载失败，请检查服务状态。";
    els.frame.style.display = "none";
  });
})();
