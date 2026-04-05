(function () {
  class Pagination {
    constructor(container, options) {
      this.container = typeof container === "string" ? document.querySelector(container) : container;
      this.options = {};
      this.update(options || {});
    }

    update(nextOptions) {
      this.options = {
        onChange: typeof nextOptions.onChange === "function" ? nextOptions.onChange : null,
        page: Math.max(1, Number(nextOptions.page || 1)),
        pageSize: Math.max(1, Number(nextOptions.page_size || nextOptions.pageSize || 20)),
        pageSizeOptions: Array.isArray(nextOptions.page_size_options) ? nextOptions.page_size_options : [10, 20, 50],
        showTotal: Boolean(nextOptions.show_total),
        totalItems: Math.max(0, Number(nextOptions.total_items || nextOptions.totalItems || 0)),
      };
      this.render();
    }

    render() {
      if (!this.container) return;
      const { onChange, page, pageSize, pageSizeOptions, showTotal, totalItems } = this.options;
      const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

      this.container.innerHTML = "";
      const root = document.createElement("div");
      root.className = "pagination";

      if (showTotal) {
        const meta = document.createElement("span");
        meta.className = "pagination-meta";
        meta.textContent = "第 " + page + " / " + totalPages + " 页，共 " + totalItems + " 条";
        root.appendChild(meta);
      }

      const prev = document.createElement("button");
      prev.type = "button";
      prev.className = "btn";
      prev.textContent = "上一页";
      prev.disabled = page <= 1;
      prev.addEventListener("click", () => {
        if (onChange) onChange(page - 1, pageSize);
      });
      root.appendChild(prev);

      const next = document.createElement("button");
      next.type = "button";
      next.className = "btn";
      next.textContent = "下一页";
      next.disabled = page >= totalPages;
      next.addEventListener("click", () => {
        if (onChange) onChange(page + 1, pageSize);
      });
      root.appendChild(next);

      const sizeSelect = document.createElement("select");
      sizeSelect.className = "pagination-size";
      pageSizeOptions.forEach((value) => {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = String(value) + " /页";
        if (Number(value) === pageSize) option.selected = true;
        sizeSelect.appendChild(option);
      });
      sizeSelect.addEventListener("change", () => {
        const nextSize = Math.max(1, Number(sizeSelect.value || pageSize));
        if (onChange) onChange(1, nextSize);
      });
      root.appendChild(sizeSelect);

      this.container.appendChild(root);
    }
  }

  window.Pagination = Pagination;
})();
