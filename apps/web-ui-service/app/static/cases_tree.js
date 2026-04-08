(function () {
  const presenter = window.CasesPresenter;
  if (!presenter) return;

  function createCasesTree(options) {
    const { els, state, onSelectionChange } = options;
    let expandedGroups = new Set();
    let knownGroups = new Set();
    let initialized = false;

    function treeGroupKey(group) {
      return `${String(group && group.project_code || "").trim()}::${String(group && group.product_line || "").trim()}`;
    }

    function visibleGroups() {
      const projectCode = String(els.filterProjectCode ? els.filterProjectCode.value : "").trim().toLowerCase();
      return (Array.isArray(state.treeItems) ? state.treeItems : [])
        .filter((group) => {
          const currentProjectCode = String(group && group.project_code || "").trim().toLowerCase();
          return !projectCode || currentProjectCode === projectCode;
        })
        .map((group) => treeGroupKey(group))
        .filter(Boolean);
    }

    function currentKeyword() {
      return String(els.treeSearch ? els.treeSearch.value : "").trim();
    }

    function syncExpandedGroups() {
      const currentGroups = visibleGroups();
      const currentGroupSet = new Set(currentGroups);
      if (!initialized) {
        expandedGroups = new Set(currentGroups);
        knownGroups = currentGroupSet;
        initialized = true;
        return;
      }
      const nextExpandedGroups = new Set();
      currentGroups.forEach((key) => {
        if (expandedGroups.has(key) || !knownGroups.has(key)) nextExpandedGroups.add(key);
      });
      expandedGroups = nextExpandedGroups;
      knownGroups = currentGroupSet;
    }

    function render() {
      const projectCode = els.filterProjectCode ? els.filterProjectCode.value : "";
      const keyword = currentKeyword();
      const filteredItems =
        keyword && typeof presenter.filterTreeItems === "function"
          ? presenter.filterTreeItems(state.treeItems, keyword, projectCode)
          : null;
      syncExpandedGroups();
      const renderItems = filteredItems || state.treeItems;
      const effectiveExpandedKeys = keyword
        ? new Set((Array.isArray(filteredItems) ? filteredItems : []).map((group) => treeGroupKey(group)))
        : expandedGroups;
      els.tree.innerHTML = presenter.treeMarkup(state.treeItems, keyword, state.treeSelection, projectCode, {
        expandedKeys: effectiveExpandedKeys,
      });
      els.treeTotal.textContent = String(presenter.totalTreeCount(renderItems, projectCode));
    }

    function bind() {
      els.tree.addEventListener("click", (event) => {
        const target = event.target instanceof Element ? event.target.closest("[data-tree-action]") : null;
        if (!target) return;
        const action = target.getAttribute("data-tree-action");
        if (action === "all") {
          onSelectionChange("", "");
          return;
        }
        if (action === "toggle-group") {
          const groupKey = String(target.getAttribute("data-tree-group") || "").trim();
          if (!groupKey) return;
          if (expandedGroups.has(groupKey)) expandedGroups.delete(groupKey);
          else expandedGroups.add(groupKey);
          render();
          return;
        }
        if (action === "product-line") {
          onSelectionChange(target.getAttribute("data-product-line") || "", "");
          return;
        }
        if (action === "module") {
          onSelectionChange(target.getAttribute("data-product-line") || "", target.getAttribute("data-module") || "");
        }
      });

      els.btnTreeClear.addEventListener("click", () => {
        document.getElementById("cases-tree-ops").open = false;
        onSelectionChange("", "");
      });
      els.btnTreeExpand.addEventListener("click", () => {
        expandedGroups = new Set(visibleGroups());
        knownGroups = new Set(visibleGroups());
        render();
        document.getElementById("cases-tree-ops").open = false;
      });
      els.btnTreeCollapse.addEventListener("click", () => {
        expandedGroups = new Set();
        knownGroups = new Set(visibleGroups());
        render();
        document.getElementById("cases-tree-ops").open = false;
      });
      if (els.treeSearch) {
        els.treeSearch.addEventListener("input", () => {
          render();
        });
        els.treeSearch.addEventListener("search", () => {
          render();
        });
      }
      if (els.btnTreeSearch) {
        els.btnTreeSearch.addEventListener("click", () => {
          render();
        });
      }
    }

    return {
      bind,
      render,
    };
  }

  window.CasesTree = {
    createCasesTree,
  };
})();
