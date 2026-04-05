(function () {
  function openDialog() {
    const name = window.prompt("请输入新用例名称：", "");
    if (name == null) return;
    const trimmedName = String(name).trim();
    if (!trimmedName) {
      window.alert("用例名称不能为空");
      return;
    }
    const productLine = window.prompt("请输入产品线（例如：电商平台）：", "电商平台");
    if (productLine == null) return;
    const moduleName = window.prompt("请输入模块（例如：商品中心）：", "商品中心");
    if (moduleName == null) return;

    const payload = {
      name: trimmedName,
      product_line: String(productLine || "").trim() || "默认产品线",
      module: String(moduleName || "").trim() || "默认模块",
      priority: "P2",
      test_type: "ui",
      tags: ["manual-draft"],
      creator: "admin",
      status: "active",
    };

    if (!window.CasesApi || typeof window.CasesApi.create !== "function") {
      window.alert("创建接口不可用，请稍后重试。");
      return;
    }

    window.CasesApi.create(payload)
      .then(() => {
        window.dispatchEvent(new CustomEvent("cases:reload"));
      })
      .catch((error) => {
        window.alert(error?.message || "创建失败");
      });
  }

  window.CasesDialog = {
    openDialog: openDialog,
  };
})();
