(function () {
  const shell = document.getElementById("report-context-shell");
  if (!shell) return;

  const els = {
    gitInfo: document.getElementById("rp-git-info"),
    buildInfo: document.getElementById("rp-build-info"),
    execInfo: document.getElementById("rp-exec-info"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderDl(target, entries) {
    target.innerHTML = entries
      .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "-")}</dd>`)
      .join("");
  }

  async function loadContext() {
    const resp = await fetch("/api/report/context");
    if (!resp.ok) {
      renderDl(els.gitInfo, [["加载失败", ""]]);
      renderDl(els.buildInfo, [["加载失败", ""]]);
      renderDl(els.execInfo, [["加载失败", ""]]);
      return;
    }
    const data = await resp.json();
    const git = data.git || {};
    const build = data.build || {};
    const exec = data.execution || {};
    renderDl(els.gitInfo, [
      ["分支", git.branch || "-"],
      ["提交ID", git.commit_id || "-"],
      ["提交信息", git.commit_message || "-"],
    ]);
    renderDl(els.buildInfo, [
      ["构建版本", build.build_version || "-"],
      ["镜像标签", build.image_tag || "-"],
      ["构建时间", build.build_time || "-"],
    ]);
    renderDl(els.execInfo, [
      ["环境", exec.environment || "-"],
      ["访问地址", exec.base_url || "-"],
      ["浏览器", exec.browser || "-"],
      ["运行器", exec.runner || "-"],
      ["最新 Run ID", exec.latest_run_id || "-"],
    ]);
  }

  loadContext().catch((error) => {
    console.error(error);
    renderDl(els.gitInfo, [["加载失败", ""]]);
    renderDl(els.buildInfo, [["加载失败", ""]]);
    renderDl(els.execInfo, [["加载失败", ""]]);
  });
})();
