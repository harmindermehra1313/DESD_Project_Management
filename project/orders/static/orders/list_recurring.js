/* ============================================================
   list_recurring.js — Recurring Orders / Subscriptions page
   ============================================================ */

/* ---------- Utility helpers ---------- */

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMoney(value) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(amount);
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getCookie(name) {
  let cookieValue = null;

  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");

    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();

      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }

  return cookieValue;
}

/* ============================================================
   Recurring Orders — table filter, pagination, modal, actions
   ============================================================ */

const RECURRING_PAGE_SIZE = 10;
let recurringCurrentPage = 1;
let recurringDetailModal = null;
let subscriptionData = [];

document.addEventListener("DOMContentLoaded", () => {
  // Parse subscription data from JSON script tag
  const dataEl = document.getElementById("subscriptionData");
  if (dataEl) {
    try { subscriptionData = JSON.parse(dataEl.textContent); } catch (_) {}
  }

  // Init recurring detail modal
  const recurringModalEl = document.getElementById("recurringDetailModal");
  if (recurringModalEl) {
    recurringDetailModal = new bootstrap.Modal(recurringModalEl);
  }

  // Bind recurring status filter checkboxes
  document.querySelectorAll(".recurring-status-filter").forEach((cb) => {
    cb.addEventListener("change", () => {
      recurringCurrentPage = 1;
      applyRecurringFilters();
    });
  });

  applyRecurringFilters();
});

function applyRecurringFilters() {
  const checked = Array.from(document.querySelectorAll(".recurring-status-filter:checked"))
    .map((cb) => cb.value);

  const rows = document.querySelectorAll(".recurring-row");

  // Filter
  const visible = [];
  rows.forEach((row) => {
    const status = row.getAttribute("data-recurring-status");
    if (checked.includes(status)) {
      visible.push(row);
    } else {
      row.classList.add("d-none");
    }
  });

  // Paginate
  const totalPages = Math.max(1, Math.ceil(visible.length / RECURRING_PAGE_SIZE));
  if (recurringCurrentPage > totalPages) recurringCurrentPage = totalPages;

  const start = (recurringCurrentPage - 1) * RECURRING_PAGE_SIZE;
  const end = start + RECURRING_PAGE_SIZE;

  visible.forEach((row, idx) => {
    if (idx >= start && idx < end) {
      row.classList.remove("d-none");
    } else {
      row.classList.add("d-none");
    }
  });

  // Pagination info
  const info = document.getElementById("recurringPaginationInfo");
  const prevBtn = document.getElementById("recurringPrevBtn");
  const nextBtn = document.getElementById("recurringNextBtn");

  if (info) {
    info.textContent = visible.length === 0
      ? "No recurring orders"
      : `Page ${recurringCurrentPage} of ${totalPages} \u00b7 ${visible.length} subscriptions`;
  }
  if (prevBtn) prevBtn.disabled = recurringCurrentPage <= 1;
  if (nextBtn) nextBtn.disabled = recurringCurrentPage >= totalPages;
}

function goToRecurringPage(delta) {
  recurringCurrentPage += delta;
  applyRecurringFilters();
}

function clearRecurringFilters() {
  document.querySelectorAll(".recurring-status-filter").forEach((cb) => {
    cb.checked = cb.value === "ACTIVE" || cb.value === "PAUSED";
  });
  recurringCurrentPage = 1;
  applyRecurringFilters();
}

/* ---------- Recurring Detail Modal ---------- */

function getSubById(subId) {
  return subscriptionData.find((s) => s.id === subId);
}

function formatSubAddress(addr) {
  if (!addr) return '<div class="text-muted">Collection from Farm</div>';
  const lines = [addr.line_1, addr.line_2, [addr.city, addr.postcode].filter(Boolean).join(" ")]
    .filter(Boolean);
  if (!lines.length) return '<div class="text-muted">Address not available</div>';
  return lines.map((l) => `<div>${escapeHtml(l)}</div>`).join("");
}

function getSubStatusBadgeClass(status) {
  if (status === "ACTIVE") return "bg-success";
  if (status === "PAUSED") return "bg-warning text-dark";
  return "bg-danger";
}

function openRecurringDetails(subId) {
  const sub = getSubById(subId);
  if (!sub) return;

  const content = document.getElementById("recurringDetailContent");
  if (!content) return;

  // Summary cards
  const summaryHtml = `
    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Subscription ID</div>
          <div class="fw-semibold">#${escapeHtml(sub.id)}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Created</div>
          <div class="fw-semibold">${formatDate(sub.created_at)}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Status</div>
          <div><span class="badge ${getSubStatusBadgeClass(sub.status)}">${escapeHtml(sub.status_display)}</span></div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Recurring</div>
          <div class="fw-semibold">&#x1F501; ${escapeHtml(sub.recurrence_pattern)} &ndash; Every ${escapeHtml(sub.recurrence_day)}</div>
        </div>
      </div>
    </div>
  `;

  // Items table
  const itemsHtml = `
    <div class="mb-4">
      <h6 class="mb-3">Items</h6>
      <div class="table-responsive">
        <table class="table table-bordered align-middle">
          <thead class="table-light">
            <tr>
              <th>Product</th>
              <th>Producer</th>
              <th>Quantity</th>
              <th>Unit Price</th>
            </tr>
          </thead>
          <tbody>
            ${(sub.items || []).map((item) => `
              <tr>
                <td>${escapeHtml(item.product_name)}</td>
                <td>${escapeHtml(item.producer_name)}</td>
                <td>${escapeHtml(item.quantity)}</td>
                <td>${formatMoney(item.price)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Delivery / collection details
  const deliveryHtml = `
    <div class="mb-4">
      <h6 class="mb-3">Delivery / Collection Details</h6>
      <div class="row g-3">
        <div class="col-12">
          <div class="border rounded p-3">
            <div class="row g-3">
              <div class="col-md-6">
                <div class="small text-muted">${sub.address_data ? "Delivery Address" : "Fulfilment"}</div>
                <div class="mt-1">${formatSubAddress(sub.address_data)}</div>
              </div>
              <div class="col-md-6">
                <div class="small text-muted">Special Instructions</div>
                <div class="mt-1 fst-italic">${escapeHtml(sub.special_instructions || "None provided.")}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Upcoming order info
  let upcomingHtml = "";
  if (sub.upcoming_order_id) {
    upcomingHtml = `
      <div class="mb-4">
        <h6 class="mb-3">Upcoming Order</h6>
        <div class="border rounded p-3">
          <span class="badge bg-info text-dark">Next order scheduled: ${formatDate(sub.upcoming_order_date)}</span>
        </div>
      </div>
    `;
  }

  // Footer with action buttons
  let footerHtml = "";
  if (sub.status !== "CANCELLED") {
    let actionButtons = "";
    if (sub.status === "ACTIVE") {
      actionButtons += `
        <button type="button"
                class="btn fw-bold"
                style="background-color: var(--dusk-blue); color: #fff; border-color: var(--dusk-blue);"
                onclick="customerPauseSubscription(${sub.id})">
          Pause Subscription
        </button>
      `;
    } else if (sub.status === "PAUSED") {
      actionButtons += `
        <button type="button"
                class="btn btn-success fw-bold"
                onclick="customerResumeSubscription(${sub.id})">
          Resume Subscription
        </button>
      `;
    }

    footerHtml = `
      <div class="border rounded p-3 d-flex justify-content-end align-items-center flex-wrap gap-2">
        ${actionButtons}
        <button type="button"
                class="btn btn-danger fw-bold"
                onclick="customerCancelSubscription(${sub.id})">
          Cancel Subscription
        </button>
      </div>
    `;
  }

  content.innerHTML = summaryHtml + itemsHtml + deliveryHtml + upcomingHtml + footerHtml;
  recurringDetailModal?.show();
}

/* ---------- Pause (Active → Paused) ---------- */

async function customerPauseSubscription(subId) {
  const sub = getSubById(subId);
  if (!sub) return;

  let cancelUpcoming = false;

  if (sub.upcoming_order_id) {
    const upcomingDateStr = sub.upcoming_order_date ? formatDate(sub.upcoming_order_date) : "soon";
    cancelUpcoming = confirm(
      `Would you like to cancel your nearest upcoming order (scheduled ${upcomingDateStr})?\n\n` +
      `Click OK to cancel the upcoming order, or Cancel to keep it.`
    );
  }

  try {
    const response = await fetch(`/orders/subscription/${subId}/toggle/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: JSON.stringify({ cancel_upcoming: cancelUpcoming }),
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "Failed to pause subscription.");
      return;
    }

    if (cancelUpcoming && data.cancelled_order_id) {
      alert("Subscription paused and the upcoming order has been cancelled.");
    } else {
      alert("Subscription paused successfully.");
    }

    location.reload();
  } catch (err) {
    alert("An error occurred. Please try again.");
  }
}

/* ---------- Resume (Paused → Active) ---------- */

async function customerResumeSubscription(subId) {
  if (!confirm("Resume this subscription? The next order will be scheduled at least 48 hours from now.")) return;

  try {
    const response = await fetch(`/orders/subscription/${subId}/toggle/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: JSON.stringify({}),
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "Failed to resume subscription.");
      return;
    }

    let msg = "Subscription resumed successfully.";
    if (data.next_delivery_date) {
      msg += `\nYour next order will be on ${formatDate(data.next_delivery_date)}.`;
    }
    alert(msg);

    location.reload();
  } catch (err) {
    alert("An error occurred. Please try again.");
  }
}

/* ---------- Cancel ---------- */

async function customerCancelSubscription(subId) {
  if (!confirm("Are you sure you want to cancel this subscription? This cannot be undone.")) return;

  try {
    const response = await fetch(`/orders/subscription/${subId}/cancel/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || "Failed to cancel subscription.");
      return;
    }

    location.reload();
  } catch (err) {
    alert("An error occurred. Please try again.");
  }
}
