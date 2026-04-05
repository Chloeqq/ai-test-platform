(function () {
  let currentStep = 1;
  let canProceedGuard = null;
  let initialized = false;

  function markers() {
    return Array.from(document.querySelectorAll("[data-step-marker]"));
  }

  function panels() {
    return Array.from(document.querySelectorAll("[data-step-panel]"));
  }

  function updateUi() {
    markers().forEach((node) => {
      const step = Number(node.getAttribute("data-step-marker") || 0);
      node.classList.toggle("is-active", step === currentStep);
      node.classList.toggle("is-complete", step < currentStep);
    });
    panels().forEach((node) => {
      const step = Number(node.getAttribute("data-step-panel") || 0);
      node.classList.toggle("is-active", step === currentStep);
    });

    const prevButton = document.getElementById("gen-step-prev");
    const nextButton = document.getElementById("gen-step-next");
    if (prevButton) prevButton.disabled = currentStep <= 1;
    if (nextButton) {
      nextButton.disabled = currentStep >= 4;
      nextButton.textContent = currentStep >= 4 ? "已完成" : "下一步";
    }
  }

  function goTo(step) {
    const nextStep = Math.min(4, Math.max(1, Number(step || 1)));
    if (typeof canProceedGuard === "function" && !canProceedGuard(currentStep, nextStep)) return false;
    currentStep = nextStep;
    updateUi();
    return true;
  }

  function setCanProceed(fn) {
    canProceedGuard = typeof fn === "function" ? fn : null;
  }

  function init() {
    if (initialized) return;
    initialized = true;
    const prevButton = document.getElementById("gen-step-prev");
    const nextButton = document.getElementById("gen-step-next");

    prevButton?.addEventListener("click", () => {
      goTo(currentStep - 1);
    });
    nextButton?.addEventListener("click", () => {
      goTo(currentStep + 1);
    });

    updateUi();
  }

  init();

  window.WorkbenchGenerateWizard = {
    goTo: goTo,
    setCanProceed: setCanProceed,
  };
})();
