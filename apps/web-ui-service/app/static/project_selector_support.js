(function () {
  function normalizeCode(value) {
    return String(value || "").trim().toLowerCase();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildOptionMarkup(items, config) {
    const projectItems = Array.isArray(items) ? items : [];
    const currentValue = normalizeCode(config && Object.prototype.hasOwnProperty.call(config, "selectedValue") ? config.selectedValue : "");
    const defaultProjectCode = normalizeCode((config && config.defaultProjectCode) || "atp") || "atp";
    const emptyOptionLabel = config && Object.prototype.hasOwnProperty.call(config, "emptyOptionLabel")
      ? String(config.emptyOptionLabel || "")
      : null;
    const includeInactive = !(config && config.includeInactive === false);
    const disableInactive = Boolean(config && config.disableInactive);
    const inactiveLabelSuffix = String(
      (config && config.inactiveLabelSuffix != null) ? config.inactiveLabelSuffix : " (inactive)"
    );
    const optionMarkup = [];

    if (emptyOptionLabel !== null) {
      const selected = currentValue ? "" : " selected";
      optionMarkup.push("<option value=\"\"" + selected + ">" + escapeHtml(emptyOptionLabel) + "</option>");
    }

    projectItems.forEach(function (item) {
      const projectCode = normalizeCode(item.project_code);
      const projectStatus = normalizeCode(item.status || "active") || "active";
      const isInactive = projectStatus !== "active";
      if (!includeInactive && isInactive) return;
      const projectName = String(item.project_name || projectCode).trim();
      const selected = projectCode === currentValue ? " selected" : "";
      const disabled = disableInactive && isInactive ? " disabled" : "";
      const displayName = isInactive ? (projectName + inactiveLabelSuffix) : projectName;
      optionMarkup.push(
        "<option value=\"" + escapeHtml(projectCode) + "\"" + selected + disabled + ">"
        + escapeHtml(projectCode) + " · " + escapeHtml(displayName)
        + "</option>"
      );
    });

    if (!optionMarkup.length) {
      optionMarkup.push("<option value=\"" + escapeHtml(defaultProjectCode) + "\" selected>"
        + escapeHtml(defaultProjectCode) + " · " + escapeHtml(defaultProjectCode.toUpperCase())
        + "</option>");
    }
    return optionMarkup.join("");
  }

  function applyProjectOptions(selectEl, items, config) {
    if (!selectEl) return [];
    const projectItems = Array.isArray(items) ? items : [];
    const defaultProjectCode = normalizeCode((config && config.defaultProjectCode) || "atp") || "atp";
    const emptyOptionLabel = config && Object.prototype.hasOwnProperty.call(config, "emptyOptionLabel")
      ? String(config.emptyOptionLabel || "")
      : null;
    const selectedValueProvided = config && Object.prototype.hasOwnProperty.call(config, "selectedValue");
    const desiredValue = normalizeCode(
      selectedValueProvided ? config.selectedValue : (selectEl.value || defaultProjectCode)
    );
    const includeInactive = !(config && config.includeInactive === false);
    const disableInactive = Boolean(config && config.disableInactive);

    const visibleProjectItems = projectItems.filter(function (item) {
      const projectStatus = normalizeCode(item.status || "active") || "active";
      const isInactive = projectStatus !== "active";
      return includeInactive ? true : !isInactive;
    });
    const selectableProjectItems = visibleProjectItems.filter(function (item) {
      if (!disableInactive) return true;
      return (normalizeCode(item.status || "active") || "active") === "active";
    });

    selectEl.innerHTML = buildOptionMarkup(projectItems, {
      selectedValue: desiredValue,
      defaultProjectCode: defaultProjectCode,
      emptyOptionLabel: emptyOptionLabel,
      includeInactive: includeInactive,
      disableInactive: disableInactive,
      inactiveLabelSuffix: config && config.inactiveLabelSuffix,
    });

    const desiredOption = desiredValue
      ? selectEl.querySelector("option[value=\"" + desiredValue + "\"]:not([disabled])")
      : (emptyOptionLabel !== null ? selectEl.querySelector("option[value=\"\"]") : null);
    if (desiredOption) {
      selectEl.value = desiredValue;
    } else if (!desiredValue && emptyOptionLabel !== null) {
      selectEl.value = "";
    } else if (selectableProjectItems.length) {
      const preferred = selectableProjectItems[0];
      selectEl.value = normalizeCode(preferred.project_code);
    } else {
      selectEl.value = "";
    }
    return visibleProjectItems;
  }

  async function loadProjectOptions(config) {
    const projectsApi = config && config.projectsApi;
    const selectEl = config && config.selectEl;
    if (!projectsApi || typeof projectsApi.list !== "function" || !selectEl) return [];
    const payload = await projectsApi.list();
    const items = Array.isArray(payload.items) ? payload.items : [];
    applyProjectOptions(selectEl, items, config || {});
    return items;
  }

  function openProjectManager(config) {
    const projectManager = config && config.projectManager;
    const projectsApi = config && config.projectsApi;
    const selectEl = config && config.selectEl;
    const onChanged = config && typeof config.onChanged === "function" ? config.onChanged : null;
    const defaultProjectCode = normalizeCode((config && config.defaultProjectCode) || "atp") || "atp";
    const deleteFallbackValue = config && Object.prototype.hasOwnProperty.call(config, "deleteFallbackValue")
      ? config.deleteFallbackValue
      : defaultProjectCode;
    if (!projectManager || typeof projectManager.open !== "function" || !projectsApi || !selectEl) return;

    const selectedProjectCode = normalizeCode(
      (config && config.selectedProjectCode) || selectEl.value || defaultProjectCode
    ) || defaultProjectCode;

    projectManager.open({
      selectedProjectCode: selectedProjectCode,
      onChanged: async function (event) {
        const action = String((event && event.action) || "").trim().toLowerCase();
        const rawProjectCode = normalizeCode(event && event.project_code);
        const selectedValue = action === "delete"
          ? String(deleteFallbackValue == null ? "" : deleteFallbackValue)
          : (rawProjectCode || defaultProjectCode);
        const items = await loadProjectOptions({
          projectsApi: projectsApi,
          selectEl: selectEl,
          selectedValue: selectedValue,
          defaultProjectCode: defaultProjectCode,
          emptyOptionLabel: config && Object.prototype.hasOwnProperty.call(config, "emptyOptionLabel")
            ? config.emptyOptionLabel
            : null,
          includeInactive: !(config && config.includeInactive === false),
          disableInactive: Boolean(config && config.disableInactive),
          inactiveLabelSuffix: config && config.inactiveLabelSuffix,
        });
        if (onChanged) {
          await Promise.resolve(onChanged({
            action: action,
            projectCode: rawProjectCode,
            selectedProjectCode: normalizeCode(selectEl.value || ""),
            items: items,
          }));
        }
      },
    });
  }

  window.ProjectSelectorSupport = {
    normalizeCode: normalizeCode,
    applyProjectOptions: applyProjectOptions,
    loadProjectOptions: loadProjectOptions,
    openProjectManager: openProjectManager,
  };
})();
