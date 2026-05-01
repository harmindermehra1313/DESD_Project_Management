document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("cookieModal");

  const functional = document.getElementById("cookieFunctional");
  const analytics = document.getElementById("cookieAnalytics");

  const acceptAll = document.getElementById("cookieAcceptAll");
  const essentialOnly = document.getElementById("cookieEssentialOnly");
  const save = document.getElementById("cookieSave");

  const consent = localStorage.getItem("cookieConsent");

  if (!consent) {
    modal.style.display = "block";
  }

  acceptAll.addEventListener("click", () => {
    localStorage.setItem("cookieConsent", JSON.stringify({
      functional: true,
      analytics: true
    }));
    modal.style.display = "none";
  });

  essentialOnly.addEventListener("click", () => {
    localStorage.setItem("cookieConsent", JSON.stringify({
      functional: false,
      analytics: false
    }));
    modal.style.display = "none";
  });

  save.addEventListener("click", () => {
    localStorage.setItem("cookieConsent", JSON.stringify({
      functional: functional.checked,
      analytics: analytics.checked
    }));
    modal.style.display = "none";
  });
});
