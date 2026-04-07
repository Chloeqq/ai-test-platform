(function () {
  function parseEpochToDate(value) {
    if (value === null || value === undefined || value === "") return null;
    const raw = typeof value === "number" ? value : Number(String(value).trim());
    if (!Number.isFinite(raw)) return null;
    const abs = Math.abs(raw);
    let epochMs = raw;
    if (abs > 0 && abs < 1e11) {
      epochMs = raw * 1000;
    } else if (abs >= 1e14 && abs < 1e17) {
      epochMs = raw / 1000;
    } else if (abs >= 1e17) {
      epochMs = raw / 1e6;
    }
    const parsed = new Date(epochMs);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  function parseDateTime(value) {
    const epochParsed = parseEpochToDate(value);
    if (epochParsed) return epochParsed;
    const text = String(value || "").trim();
    if (!text) return null;
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatDateTime(value, fallback) {
    const parsed = parseDateTime(value);
    if (!parsed) {
      const text = String(value || "").trim();
      return text || fallback || "-";
    }
    return [
      parsed.getFullYear(),
      pad(parsed.getMonth() + 1),
      pad(parsed.getDate()),
    ].join("-") + " " + [
      pad(parsed.getHours()),
      pad(parsed.getMinutes()),
      pad(parsed.getSeconds()),
    ].join(":");
  }

  function formatDateRange(start, end, fallback) {
    const startText = formatDateTime(start, "");
    const endText = formatDateTime(end, "");
    if (!startText || !endText) return fallback || "-";
    return startText + " ~ " + endText;
  }

  function normalizeCaseId(value) {
    const text = String(value || "")
      .trim()
      .replace(/^['"]|['"]$/g, "")
      .replace(/[_\s]+/g, "-")
      .replace(/[^A-Za-z0-9-]/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase();
    return text;
  }

  function displayCaseId(value, fallback) {
    const normalized = normalizeCaseId(value);
    if (normalized) return normalized;
    const text = String(value || "").trim();
    return text || fallback || "-";
  }

  function splitRunId(value) {
    const text = String(value || "").trim();
    if (!text) return { raw: "", caseId: "", startedAt: "" };
    const index = text.indexOf(":");
    if (index < 0) return { raw: text, caseId: "", startedAt: "" };
    return {
      raw: text,
      caseId: normalizeCaseId(text.slice(0, index)),
      startedAt: text.slice(index + 1).trim(),
    };
  }

  function displayRunId(value, fallback) {
    const parsed = splitRunId(value);
    if (!parsed.raw) return fallback || "-";
    if (!parsed.caseId) return parsed.raw;
    const timeText = formatDateTime(parsed.startedAt, "");
    return timeText ? `${parsed.caseId} · ${timeText}` : parsed.caseId;
  }

  const MODULE_LABELS = {
    auth: "登录认证",
    permission: "权限管理",
    product: "商品管理",
    "product-list": "列表展示",
    order: "订单列表",
    brand: "品牌管理",
    coupon: "优惠券管理",
    flash: "秒杀活动",
    returnapply: "查询检索",
    payment: "支付处理",
    "oms-order-setting": "配置管理",
    "sms-brand": "品牌管理",
    "sms-coupon": "优惠券管理",
    "oms-return-apply": "查询检索",
    addproduct: "商品新增",
  };

  const TAG_LABELS = {
    smoke: "冒烟",
    regression: "回归",
    functional: "功能",
    "ai-generated": "AI生成",
    fallback: "回退",
    product: "商品",
    order: "订单",
    brand: "品牌",
    coupon: "优惠券",
    payment: "支付",
    permission: "权限",
    returnapply: "退货申请",
    addproduct: "商品新增",
    search: "查询",
    accessibility: "可访问性",
    "core-flow": "核心流程",
    ui: "界面",
    oms: "订单域",
    pms: "商品域",
    openapi: "接口契约",
  };

  const TEST_TYPE_LABELS = {
    ui: "界面测试",
    api: "接口测试",
    mobile: "移动端测试",
    database: "数据库测试",
  };

  const STATUS_LABELS = {
    active: "启用",
    inactive: "停用",
    deprecated: "已废弃",
    automated: "已自动化",
  };

  function displayModule(value, fallback) {
    const text = String(value || "").trim();
    if (!text) return fallback || "-";
    return MODULE_LABELS[text] || text;
  }

  function displayTag(value, fallback) {
    const text = String(value || "").trim();
    if (!text) return fallback || "-";
    return TAG_LABELS[text] || text;
  }

  function displayTagList(values, fallback) {
    const items = Array.isArray(values) ? values : [];
    const normalized = items.map((item) => displayTag(item, "")).filter(Boolean);
    return normalized.length ? normalized.join("、") : (fallback || "-");
  }

  function displayTestType(value, fallback) {
    const text = String(value || "").trim();
    if (!text) return fallback || "-";
    return TEST_TYPE_LABELS[text] || text;
  }

  function displayStatus(value, fallback) {
    const text = String(value || "").trim();
    if (!text) return fallback || "-";
    return STATUS_LABELS[text] || text;
  }

  function formatRefreshTime(value, fallback) {
    const formatted = formatDateTime(value, "");
    return formatted ? `最后刷新：${formatted}` : (fallback || "最后刷新：-");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderBadge(value, fallback) {
    const text = String(value || fallback || "unknown").trim() || fallback || "unknown";
    const cls = text.toLowerCase().replaceAll(/[^a-z0-9_]+/g, "_");
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function paginateItems(items, page, pageSize) {
    const list = Array.isArray(items) ? items : [];
    const normalizedPageSize = Math.max(1, Number(pageSize || 20) || 20);
    const totalItems = list.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / normalizedPageSize));
    const normalizedPage = Math.min(Math.max(1, Number(page || 1) || 1), totalPages);
    const start = (normalizedPage - 1) * normalizedPageSize;
    return {
      items: list.slice(start, start + normalizedPageSize),
      page: normalizedPage,
      pageSize: normalizedPageSize,
      totalItems,
      totalPages,
      start: totalItems ? start + 1 : 0,
      end: Math.min(start + normalizedPageSize, totalItems),
    };
  }

  function renderSimplePagination(container, state, onChange) {
    if (!container) return;
    const meta = paginateItems([], state.page, state.pageSize);
    const page = Number(state.page || meta.page || 1);
    const pageSize = Number(state.pageSize || meta.pageSize || 20);
    const totalItems = Number(state.totalItems || 0);
    const totalPages = Math.max(1, Number(state.totalPages || 1));
    const options = [10, 20, 50, 100]
      .map((value) => `<option value="${value}" ${value === pageSize ? "selected" : ""}>${value}/页</option>`)
      .join("");
    container.innerHTML = `
      <div class="table-footer-meta">共 ${totalItems} 条，当前第 ${page}/${totalPages} 页</div>
      <div class="table-footer-actions">
        <label class="footer-page-size">每页<select data-role="page-size">${options}</select></label>
        <button type="button" class="btn" data-role="prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
        <button type="button" class="btn" data-role="next" ${page >= totalPages ? "disabled" : ""}>下一页</button>
      </div>
    `;
    const pageSizeSelect = container.querySelector('[data-role="page-size"]');
    const prevBtn = container.querySelector('[data-role="prev"]');
    const nextBtn = container.querySelector('[data-role="next"]');
    if (pageSizeSelect) {
      pageSizeSelect.addEventListener("change", () => onChange(1, Number(pageSizeSelect.value || 20)));
    }
    if (prevBtn) prevBtn.addEventListener("click", () => onChange(Math.max(1, page - 1), pageSize));
    if (nextBtn) nextBtn.addEventListener("click", () => onChange(Math.min(totalPages, page + 1), pageSize));
  }

  function normalizeFilterFieldMap(fields) {
    return Object.entries(fields || {}).filter(([, element]) => element && typeof element.value !== "undefined");
  }

  function collectFilterValues(fields, normalizers) {
    const values = {};
    normalizeFilterFieldMap(fields).forEach(([key, element]) => {
      const normalizer = normalizers && normalizers[key];
      values[key] = typeof normalizer === "function"
        ? normalizer(element.value, element, key)
        : String(element.value || "").trim();
    });
    return values;
  }

  function hasActiveFilterValues(values, keys) {
    const source = values && typeof values === "object" ? values : {};
    const targetKeys = Array.isArray(keys) && keys.length ? keys : Object.keys(source);
    return targetKeys.some((key) => {
      const value = source[key];
      if (Array.isArray(value)) return value.some((item) => String(item || "").trim());
      return Boolean(String(value || "").trim());
    });
  }

  function setDetailsOpen(element, isOpen) {
    if (element && typeof element.open !== "undefined") {
      element.open = Boolean(isOpen);
    }
  }

  function renderFilterSummary(element, activeFilters, options) {
    if (!element) return;
    const config = options || {};
    const totalItems = Math.max(0, Number(config.totalItems || 0));
    const parts = (Array.isArray(activeFilters) ? activeFilters : [])
      .map((item) => {
        if (item && typeof item === "object") {
          const label = String(item.label || "").trim();
          const value = String(item.value || "").trim();
          if (label && value) return `${label} ${value}`;
          return label || value;
        }
        return String(item || "").trim();
      })
      .filter(Boolean);
    const prefix = String(config.prefix || "当前筛选：");
    const hitText = typeof config.hitText === "function"
      ? config.hitText(totalItems)
      : String(config.hitText || `命中 ${totalItems} 项`);
    const emptyText = typeof config.emptyText === "function"
      ? config.emptyText(totalItems)
      : String(config.emptyText || `当前按默认条件展示全部数据，共 ${totalItems} 项`);
    element.textContent = parts.length ? `${prefix}${parts.join(" / ")}，${hitText}` : emptyText;
  }

  function setRefreshTime(element, value, fallback) {
    if (!element) return;
    element.textContent = formatRefreshTime(value, fallback);
  }

  function syncSelectionBar(selectionBar, selectionCopy, count, options) {
    const total = Math.max(0, Number(count || 0));
    if (selectionBar) selectionBar.hidden = total === 0;
    if (!selectionCopy) return total;
    const config = options || {};
    selectionCopy.textContent = typeof config.copyText === "function"
      ? config.copyText(total)
      : `已选择 ${total} 项`;
    return total;
  }

  async function copyText(text) {
    const content = String(text || "");
    if (!content) return false;
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(content);
      return true;
    }
    const textarea = document.createElement("textarea");
    textarea.value = content;
    textarea.setAttribute("readonly", "readonly");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    return copied;
  }

  function readFilterState(storageKey, fields) {
    const params = new URLSearchParams(window.location.search || "");
    const fieldEntries = normalizeFilterFieldMap(fields);
    const fromQuery = {};
    fieldEntries.forEach(([key]) => {
      const value = params.get(key);
      if (value !== null) fromQuery[key] = value;
    });
    if (Object.keys(fromQuery).length) return fromQuery;
    if (!storageKey) return {};
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function writeFilterState(storageKey, fields) {
    const fieldEntries = normalizeFilterFieldMap(fields);
    const payload = {};
    const params = new URLSearchParams(window.location.search || "");
    fieldEntries.forEach(([key, element]) => {
      const value = String(element.value || "").trim();
      if (value) {
        payload[key] = value;
        params.set(key, value);
      } else {
        params.delete(key);
      }
    });
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash || ""}`;
    window.history.replaceState({}, "", nextUrl);
    if (!storageKey) return payload;
    try {
      if (Object.keys(payload).length) window.sessionStorage.setItem(storageKey, JSON.stringify(payload));
      else window.sessionStorage.removeItem(storageKey);
    } catch (_error) {
      // ignore sessionStorage failures
    }
    return payload;
  }

  function restoreFilterState(storageKey, fields) {
    const values = readFilterState(storageKey, fields);
    normalizeFilterFieldMap(fields).forEach(([key, element]) => {
      if (typeof values[key] !== "undefined") {
        element.value = values[key];
      }
    });
    writeFilterState(storageKey, fields);
    return values;
  }

  function clearFilterState(storageKey) {
    const params = new URLSearchParams(window.location.search || "");
    Array.from(params.keys()).forEach((key) => params.delete(key));
    const nextUrl = `${window.location.pathname}${window.location.hash || ""}`;
    window.history.replaceState({}, "", nextUrl);
    if (!storageKey) return;
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch (_error) {
      // ignore sessionStorage failures
    }
  }

  window.platformParseDateTime = parseDateTime;
  window.platformFormatDateTime = formatDateTime;
  window.platformFormatDateRange = formatDateRange;
  window.platformFormatRefreshTime = formatRefreshTime;
  window.platformPaginateItems = paginateItems;
  window.platformRenderSimplePagination = renderSimplePagination;
  window.platformNormalizeCaseId = normalizeCaseId;
  window.platformDisplayCaseId = displayCaseId;
  window.platformSplitRunId = splitRunId;
  window.platformDisplayRunId = displayRunId;
  window.platformDisplayModule = displayModule;
  window.platformDisplayTag = displayTag;
  window.platformDisplayTagList = displayTagList;
  window.platformDisplayTestType = displayTestType;
  window.platformDisplayStatus = displayStatus;
  window.platformEscapeHtml = escapeHtml;
  window.platformRenderBadge = renderBadge;
  window.platformReadFilterState = readFilterState;
  window.platformWriteFilterState = writeFilterState;
  window.platformRestoreFilterState = restoreFilterState;
  window.platformClearFilterState = clearFilterState;
  window.platformCollectFilterValues = collectFilterValues;
  window.platformHasActiveFilterValues = hasActiveFilterValues;
  window.platformSetDetailsOpen = setDetailsOpen;
  window.platformRenderFilterSummary = renderFilterSummary;
  window.platformSetRefreshTime = setRefreshTime;
  window.platformSyncSelectionBar = syncSelectionBar;
  window.platformCopyText = copyText;
})();
