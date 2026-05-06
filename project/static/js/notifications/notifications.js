document.addEventListener("DOMContentLoaded", function () {
  const panels = document.querySelectorAll("[data-notifications-auto-panel]");
  const headers = document.querySelectorAll("[data-notifications-header]");

  if (!panels.length && !headers.length) {
    return;
  }

  const DEFAULT_INTERVAL = 15000;
  const PROFILE_NOTIFICATION_ANCHOR = "profile-notifications";
  const PROFILE_PAGE_PARAM = "notifications_page";

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

  function getCurrentProfileNotificationPage() {
    const params = new URLSearchParams(window.location.search);
    const pageFromUrl = params.get(PROFILE_PAGE_PARAM);

    if (pageFromUrl) {
      return pageFromUrl;
    }

    const firstPanel = document.querySelector("[data-notifications-auto-panel]");
    return firstPanel?.dataset.notificationsPage || "1";
  }

  function buildProfileNotificationUrl(pageNumber) {
    const url = new URL(window.location.href);

    url.searchParams.delete("page");
    url.searchParams.set(PROFILE_PAGE_PARAM, pageNumber);
    url.hash = PROFILE_NOTIFICATION_ANCHOR;

    return `${url.pathname}${url.search}${url.hash}`;
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

  function updateProfileHiddenInputs(root) {
    const oldPageInputs = root.querySelectorAll('input[name="page"]');

    oldPageInputs.forEach(function (input) {
      input.name = PROFILE_PAGE_PARAM;
    });

    const pageInputs = root.querySelectorAll(
      `input[name="${PROFILE_PAGE_PARAM}"]`,
    );

    pageInputs.forEach(function (input) {
      const currentPage = getCurrentProfileNotificationPage();
      input.value = currentPage;
    });
  }

  function updateProfilePaginationLinks(root) {
    const links = root.querySelectorAll("a[href]");

    links.forEach(function (link) {
      try {
        const url = new URL(link.href, window.location.origin);
        const oldPage = url.searchParams.get("page");
        const newPage = url.searchParams.get(PROFILE_PAGE_PARAM);

        const targetPage = newPage || oldPage;

        if (!targetPage) {
          return;
        }

        link.href = buildProfileNotificationUrl(targetPage);
      } catch (error) {
      }
    });
  }

  function createCompactPagination(currentPage, totalPages) {
    const nav = document.createElement("nav");
    nav.className = "mt-3";
    nav.setAttribute("aria-label", "Notification pagination");

    const wrapper = document.createElement("div");
    wrapper.className =
      "d-flex justify-content-between align-items-center gap-2 flex-wrap";

    const previous = document.createElement(currentPage > 1 ? "a" : "button");
    previous.className = "btn btn-sm btn-outline-secondary flex-fill";
    previous.textContent = "Previous";

    if (currentPage > 1) {
      previous.href = buildProfileNotificationUrl(currentPage - 1);
    } else {
      previous.type = "button";
      previous.disabled = true;
    }

    const label = document.createElement("span");
    label.className = "small text-muted text-center flex-shrink-0 px-2";
    label.textContent = `Page ${currentPage} of ${totalPages}`;

    const next = document.createElement(currentPage < totalPages ? "a" : "button");
    next.className = "btn btn-sm btn-outline-secondary flex-fill";
    next.textContent = "Next";

    if (currentPage < totalPages) {
      next.href = buildProfileNotificationUrl(currentPage + 1);
    } else {
      next.type = "button";
      next.disabled = true;
    }

    wrapper.appendChild(previous);
    wrapper.appendChild(label);
    wrapper.appendChild(next);
    nav.appendChild(wrapper);

    return nav;
  }

  function getPaginationNumbers(pagination) {
    const numbers = [];

    pagination.querySelectorAll(".page-link").forEach(function (link) {
      const text = link.textContent.trim();
      const number = Number(text);

      if (Number.isInteger(number) && number > 0) {
        numbers.push(number);
      }
    });

    return numbers;
  }

  function getActivePageNumber(pagination) {
    const activeLink = pagination.querySelector(".page-item.active .page-link");
    const activeNumber = Number(activeLink?.textContent.trim());

    if (Number.isInteger(activeNumber) && activeNumber > 0) {
      return activeNumber;
    }

    const currentPage = Number(getCurrentProfileNotificationPage());

    return Number.isInteger(currentPage) && currentPage > 0
      ? currentPage
      : 1;
  }

  function replaceNumberedPagination(root) {
    const oldPagination = root.querySelector(".pagination");

    if (!oldPagination) {
      return;
    }

    const numbers = getPaginationNumbers(oldPagination);

    if (!numbers.length) {
      return;
    }

    const currentPage = getActivePageNumber(oldPagination);
    const totalPages = Math.max(...numbers);
    const compactPagination = createCompactPagination(currentPage, totalPages);
    const oldNav = oldPagination.closest("nav") || oldPagination;

    oldNav.replaceWith(compactPagination);
  }

  function normaliseProfileNotificationPanel(root) {
    updateProfileHiddenInputs(root);
    updateProfilePaginationLinks(root);
    replaceNumberedPagination(root);
  }

  function updatePanels(data) {
    panels.forEach(function (panel) {
      if (!data.success || typeof data.html !== "string") {
        return;
      }

      panel.innerHTML = data.html;

      panel.dataset.notificationsPage =
        data.page ||
        getCurrentProfileNotificationPage() ||
        panel.dataset.notificationsPage ||
        "1";

      normaliseProfileNotificationPanel(panel);
    });
  }

  async function refreshNotifications() {
    const url = getFirstUrl();

    if (!url) {
      return;
    }

    const page = getCurrentProfileNotificationPage();

    const params = new URLSearchParams({
      page: page,
      notifications_page: page,
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

  panels.forEach(function (panel) {
    normaliseProfileNotificationPanel(panel);
  });

  refreshNotifications();

  setInterval(function () {
    refreshNotifications();
  }, getFirstInterval());
});