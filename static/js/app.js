if ("serviceWorker" in navigator && location.protocol !== "file:") {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/pwa/sw.js").catch(() => {});
  });
}
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"], button:not([type])');
      if (button && form.checkValidity()) {
        button.dataset.originalText = button.textContent;
        button.disabled = true;
        button.textContent = "Please wait…";
        window.setTimeout(() => {
          button.disabled = false;
          button.textContent = button.dataset.originalText || "Submit";
        }, 5000);
      }
    });
  });
});
