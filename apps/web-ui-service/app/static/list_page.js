(function () {
  function mountSearchField(config) {
    const input = config?.input || null;
    if (!input) return;
    const clearButton = config?.clearButton || null;
    const searchButton = config?.searchButton || null;
    const onSearch = typeof config?.onSearch === "function" ? config.onSearch : null;

    function syncClearButton() {
      if (!clearButton) return;
      const hasValue = String(input.value || "").trim().length > 0;
      clearButton.hidden = !hasValue;
    }

    input.addEventListener("input", syncClearButton);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        if (onSearch) onSearch();
      }
    });

    if (clearButton) {
      clearButton.addEventListener("click", () => {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.focus();
        if (onSearch) onSearch();
      });
      syncClearButton();
    }

    if (searchButton) {
      searchButton.addEventListener("click", () => {
        if (onSearch) onSearch();
      });
    }
  }

  function bindSortHeaders(config) {
    const root = config?.container || config?.root || document;
    const keyInput = config?.keyInput || config?.sortKeyInput || null;
    const dirInput = config?.dirInput || config?.sortDirInput || null;
    const onChange = typeof config?.onChange === "function" ? config.onChange : null;
    if (!root || !keyInput || !dirInput) return;

    const buttons = Array.from(root.querySelectorAll("[data-sort-key]"));
    if (!buttons.length) return;

    function syncButtonState() {
      const key = String(keyInput.value || "");
      const dir = String(dirInput.value || "desc").toLowerCase();
      buttons.forEach((button) => {
        const buttonKey = String(button.getAttribute("data-sort-key") || "");
        if (buttonKey === key) {
          button.setAttribute("data-sort-dir", dir);
          button.setAttribute("aria-sort", dir === "asc" ? "ascending" : "descending");
        } else {
          button.removeAttribute("data-sort-dir");
          button.removeAttribute("aria-sort");
        }
      });
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const nextKey = String(button.getAttribute("data-sort-key") || "").trim();
        if (!nextKey) return;
        const defaultDir = String(button.getAttribute("data-sort-default") || "asc").toLowerCase() === "desc" ? "desc" : "asc";
        const currentKey = String(keyInput.value || "");
        const currentDir = String(dirInput.value || "desc").toLowerCase() === "asc" ? "asc" : "desc";
        keyInput.value = nextKey;
        if (currentKey !== nextKey) {
          dirInput.value = defaultDir;
        } else {
          dirInput.value = currentDir === "asc" ? "desc" : "asc";
        }
        syncButtonState();
        if (onChange) onChange();
      });
    });

    syncButtonState();
  }

  window.ListPage = {
    mountSearchField: mountSearchField,
    bindSortHeaders: bindSortHeaders,
  };
})();
