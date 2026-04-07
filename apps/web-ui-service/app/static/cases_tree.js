(function () {
  const presenter = window.CasesPresenter;
  if (!presenter) return;

  function createCasesTree(options) {
    const { els, state, onSelectionChange } = options;

    function render() {
      const projectCode = els.filterProjectCode ? els.filterProjectCode.value : "";
      els.tree.innerHTML = presenter.treeMarkup(state.treeItems, "", state.treeSelection, projectCode);
      els.treeTotal.textContent = String(presenter.totalTreeCount(state.treeItems, projectCode));
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
        els.tree.querySelectorAll(".cases-tree-group").forEach((node) => {
          node.open = true;
        });
        document.getElementById("cases-tree-ops").open = false;
      });
      els.btnTreeCollapse.addEventListener("click", () => {
        els.tree.querySelectorAll(".cases-tree-group").forEach((node) => {
          node.open = false;
        });
        document.getElementById("cases-tree-ops").open = false;
      });
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
