document.addEventListener("DOMContentLoaded", function () {
  const panels = document.querySelectorAll("[data-notifications-auto-panel]");
  const headers = document.querySelectorAll("[data-notifications-header]");

  if (!panels.length && !headers.length) {
    return;
  }

  const DEFAULT_INTERVAL = 15000;

  function getFirstUrl() {
    const panelWithUrl = document.querySelector(
      "[data-notifications-auto-panel][data-notifications-url]",
    );
    const headerWithUrl = document.querySelector(
      "[data-notifications-header][data-notifications-url]",
    );

    if (panelWithUrl) {
      return panelWithUrl.dataset.notificationsUrl;
    }

    if (headerWithUrl) {
      return headerWithUrl.dataset.notificationsUrl;
    }

    return null;
  }

  function getFirstInterval() {
    const source =
      document.querySelector(
        "[data-notifications-header][data-notifications-interval]",
      ) ||
      document.querySelector(
        "[data-notifications-auto-panel][data-notifications-interval]",
      );

    const interval = Number(
      source?.dataset.notificationsInterval || DEFAULT_INTERVAL,
    );

    return Number.isFinite(interval) && interval >= 5000
      ? interval
      : DEFAULT_INTERVAL;
  }

  function updateHeaderUnreadCount(unreadCount) {
    const count = Number(unreadCount || 0);

    headers.forEach(function (header) {
      const dots = header.querySelectorAll("[data-notifications-dot]");
      const badges = header.querySelectorAll(
        "[data-notifications-count-badge]",
      );
      const countTexts = header.querySelectorAll("[data-notifications-count]");

      countTexts.forEach(function (countText) {
        countText.textContent = count;
      });

      dots.forEach(function (dot) {
        dot.classList.toggle("d-none", count === 0);
      });

      badges.forEach(function (badge) {
        badge.classList.toggle("d-none", count === 0);
      });
    });
  }

  function updatePanels(data) {
    panels.forEach(function (panel) {
      if (!data.success || typeof data.html !== "string") {
        return;
      }

      panel.innerHTML = data.html;
      panel.dataset.notificationsPage =
        data.page || panel.dataset.notificationsPage || "1";
    });
  }

  async function refreshNotifications() {
    const url = getFirstUrl();

    if (!url) {
      return;
    }

    const firstPanel = document.querySelector(
      "[data-notifications-auto-panel]",
    );
    const page = firstPanel?.dataset.notificationsPage || "1";

    const params = new URLSearchParams({
      page: page,
    });

    try {
      const response = await fetch(`${url}?${params.toString()}`, {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      if (!data.success) {
        return;
      }

      updateHeaderUnreadCount(data.unread_count);
      updatePanels(data);
    } catch (error) {
    }
  }

  refreshNotifications();

  setInterval(function () {
    refreshNotifications();
  }, getFirstInterval());
});
