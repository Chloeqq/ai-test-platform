(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function createCasesTree(config) {
    const els = config.els;
    const state = config.state;
    const onSelectionChange = typeof config.onSelectionChange === "function" ? config.onSelectionChange : () => {};

    function isProductSelected(productLine) {
      return state.treeSelection?.product_line === productLine && !state.treeSelection?.module;
    }

    function isModuleSelected(productLine, module) {
      return state.treeSelection?.product_line === productLine && state.treeSelection?.module === module;
    }

    function render() {
      const items = Array.isArray(state.treeItems) ? state.treeItems : [];
      if (els.treeTotal) els.treeTotal.textContent = String(items.length);
      if (!els.tree) return;
      if (!items.length) {
        els.tree.innerHTML = '<div class="empty-state">暂无模块树数据。</div>';
        return;
      }

      els.tree.innerHTML = items
        .map((group) => {
          const productLine = String(group.product_line || "");
          const modules = Array.isArray(group.modules) ? group.modules : [];
          return (
            '<section class="cases-tree-group">' +
            '<button type="button" class="cases-tree-product' +
            (isProductSelected(productLine) ? " is-active" : "") +
            '" data-tree-product="' +
            escapeHtml(productLine) +
            '">' +
            escapeHtml(productLine || "未分组") +
            "</button>" +
            '<div class="cases-tree-modules">' +
            modules
              .map((module) => {
                const moduleName = String(module || "");
                return (
                  '<button type="button" class="cases-tree-module' +
                  (isModuleSelected(productLine, moduleName) ? " is-active" : "") +
                  '" data-tree-product="' +
                  escapeHtml(productLine) +
                  '" data-tree-module="' +
                  escapeHtml(moduleName) +
                  '">' +
                  escapeHtml(moduleName || "未命名模块") +
                  "</button>"
                );
              })
              .join("") +
            "</div>" +
            "</section>"
          );
        })
        .join("");
    }

    function bind() {
      if (!els.tree) return;
      els.tree.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const moduleButton = target.closest("[data-tree-module]");
        if (moduleButton) {
          const product = String(moduleButton.getAttribute("data-tree-product") || "");
          const module = String(moduleButton.getAttribute("data-tree-module") || "");
          onSelectionChange(product, module);
          return;
        }
        const productButton = target.closest("[data-tree-product]");
        if (!productButton) return;
        const product = String(productButton.getAttribute("data-tree-product") || "");
        onSelectionChange(product, "");
      });
    }

    return {
      bind: bind,
      render: render,
    };
  }

  window.CasesTree = {
    createCasesTree: createCasesTree,
  };
})();
