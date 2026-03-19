(function () {
  const shell = document.getElementById("report-allure-shell");
  if (!shell) return;

  const els = {
    status: document.getElementById("rp-allure-status"),
    frame: document.getElementById("rp-allure-frame"),
  };

  async function loadAllure() {
    const resp = await fetch("/api/report/allure");
    if (!resp.ok) {
      els.status.textContent = "加载失败，请检查服务状态。";
      els.frame.style.display = "none";
      return;
    }
    const data = await resp.json();
    if (data.available) {
      els.status.textContent = "Allure 报告已就绪。";
      els.frame.style.display = "block";
      els.frame.setAttribute("src", data.allure_index || "/allure/index.html");
    } else {
      els.status.textContent = "暂未生成 Allure 报告，请先执行用例。";
      els.frame.style.display = "none";
    }
  }

  loadAllure().catch((error) => {
    console.error(error);
    els.status.textContent = "加载失败，请检查服务状态。";
    els.frame.style.display = "none";
  });
})();
