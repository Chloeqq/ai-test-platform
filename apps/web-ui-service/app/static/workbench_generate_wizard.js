(function () {
  const shell = document.getElementById("workbench-generate-shell");
  if (!shell) return;

  const panels = Array.from(shell.querySelectorAll("[data-step-panel]"));
  const markers = Array.from(shell.querySelectorAll("[data-step-marker]"));
  const prevButton = document.getElementById("gen-step-prev");
  const nextButton = document.getElementById("gen-step-next");
  if (!panels.length || !markers.length || !prevButton || !nextButton) return;

  let currentStep = 1;
  const maxStep = panels.length;
  let canProceed = null;

  function nextStepBlocked() {
    if (currentStep === maxStep) return true;
    if (typeof canProceed !== "function") return false;
    return canProceed(currentStep, currentStep + 1) === false;
  }

  function sync() {
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", Number(panel.dataset.stepPanel) === currentStep);
    });
    markers.forEach((marker) => {
      marker.classList.toggle("is-active", Number(marker.dataset.stepMarker) === currentStep);
      marker.classList.toggle("is-complete", Number(marker.dataset.stepMarker) < currentStep);
    });
    prevButton.disabled = currentStep === 1;
    nextButton.disabled = nextStepBlocked();
    if (currentStep === maxStep) {
      nextButton.textContent = "已到最后一步";
    } else if (nextButton.disabled) {
      nextButton.textContent = "请先完成当前步骤";
    } else {
      nextButton.textContent = "下一步";
    }
  }

  prevButton.addEventListener("click", () => {
    currentStep = Math.max(1, currentStep - 1);
    sync();
  });

  nextButton.addEventListener("click", () => {
    currentStep = Math.min(maxStep, currentStep + 1);
    sync();
  });

  window.WorkbenchGenerateWizard = {
    currentStep() {
      return currentStep;
    },
    goTo(step) {
      currentStep = Math.min(maxStep, Math.max(1, Number(step) || 1));
      sync();
    },
    setCanProceed(callback) {
      canProceed = typeof callback === "function" ? callback : null;
      sync();
    },
  };

  sync();
})();
