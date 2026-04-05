(function () {
  function safeParseDate(value) {
    if (!value) return null;
    if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
    const date = new Date(String(value));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatDateTime(value, fallback) {
    const fb = fallback || "-";
    const date = safeParseDate(value);
    if (!date) return fb;
    try {
      return new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch (_error) {
      return date.toISOString().replace("T", " ").slice(0, 16);
    }
  }

  function formatDateRange(start, end, fallback) {
    const fb = fallback || "-";
    const startText = formatDateTime(start, "");
    const endText = formatDateTime(end, "");
    if (!startText && !endText) return fb;
    if (!startText) return endText;
    if (!endText) return startText;
    return startText + " - " + endText;
  }

  function toValueMap(nodesByKey) {
    const payload = {};
    if (!nodesByKey || typeof nodesByKey !== "object") return payload;
    Object.keys(nodesByKey).forEach((key) => {
      const node = nodesByKey[key];
      if (!node) return;
      payload[key] = String(node.value || "");
    });
    return payload;
  }

  function restoreValueMap(nodesByKey, payload) {
    if (!nodesByKey || typeof nodesByKey !== "object") return;
    if (!payload || typeof payload !== "object") return;
    Object.keys(nodesByKey).forEach((key) => {
      if (!(key in payload)) return;
      const node = nodesByKey[key];
      if (!node) return;
      node.value = String(payload[key] || "");
    });
  }

  function readFilterState(storageKey) {
    if (!storageKey || typeof window.localStorage === "undefined") return {};
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function writeFilterState(storageKey, nodesByKey) {
    if (!storageKey || typeof window.localStorage === "undefined") return;
    try {
      const payload = toValueMap(nodesByKey);
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
    } catch (_error) {
      // Ignore storage errors in private mode / quota exceeded.
    }
  }

  function restoreFilterState(storageKey, nodesByKey) {
    const payload = readFilterState(storageKey);
    restoreValueMap(nodesByKey, payload);
  }

  function renderSimplePagination(container, pageInfo, onChange) {
    if (!container) return;
    const page = Math.max(1, Number(pageInfo?.page || 1));
    const pageSize = Math.max(1, Number(pageInfo?.pageSize || pageInfo?.page_size || 20));
    const totalItems = Math.max(0, Number(pageInfo?.totalItems || pageInfo?.total_items || 0));
    const totalPages = Math.max(1, Number(pageInfo?.totalPages || pageInfo?.total_pages || Math.ceil(totalItems / pageSize) || 1));

    container.innerHTML = "";
    const shell = document.createElement("div");
    shell.className = "button-row";

    const meta = document.createElement("span");
    meta.className = "inline-tip";
    meta.textContent = "第 " + page + " / " + totalPages + " 页 · 共 " + totalItems + " 条";
    shell.appendChild(meta);

    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn";
    prev.textContent = "上一页";
    prev.disabled = page <= 1;
    prev.addEventListener("click", () => {
      if (typeof onChange === "function") onChange(page - 1, pageSize);
    });
    shell.appendChild(prev);

    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn";
    next.textContent = "下一页";
    next.disabled = page >= totalPages;
    next.addEventListener("click", () => {
      if (typeof onChange === "function") onChange(page + 1, pageSize);
    });
    shell.appendChild(next);

    container.appendChild(shell);
  }

  window.platformFormatDateTime = formatDateTime;
  window.platformFormatDateRange = formatDateRange;
  window.platformReadFilterState = readFilterState;
  window.platformWriteFilterState = writeFilterState;
  window.platformRestoreFilterState = restoreFilterState;
  window.platformRenderSimplePagination = renderSimplePagination;
})();
