let selectedSummaryId = null;
let pendingStatusValue = null;
let pendingStatusLabel = null;

const STATUS_CONFIRMATION_HELP = {
  PRE: "Use this when work has started on this producer's items.",
  PAC: "Use this only when all items in this producer section have been packed.",
  RFC: "Use this only when a collection order is packed and ready for the customer to collect.",
  SHP: "Use this only when a delivery order has left the producer for delivery.",
  COM: "Use this only when the producer section has been fully fulfilled.",
};

// Pagination variables
let currentPage = 1;
let subCurrentPage = 1;
const rowsPerPage = 10;

const PRODUCER_STATUS_MAP = {
  PEN: { text: "Pending", cls: "status-pending" },
  PRE: { text: "Preparing", cls: "status-preparing" },
  PAC: { text: "Packaged", cls: "status-packaged" },
  RFC: { text: "Ready for collection", cls: "status-ready" },
  SHP: { text: "Shipped", cls: "status-shipped" },
  COM: { text: "Completed", cls: "status-completed" },
  CAN: { text: "Cancelled", cls: "status-cancelled" },
};

function getProducerStatusInfo(status, fallbackText = null) {
  return (
    PRODUCER_STATUS_MAP[status] || {
      text: fallbackText || status,
      cls: "status-pending",
    }
  );
}

function parseAllowedStatuses(rowElement) {
  if (!rowElement) return [];

  try {
    return JSON.parse(rowElement.getAttribute("data-allowed-statuses") || "[]");
  } catch (error) {
    console.error("Invalid allowed status JSON:", error);
    return [];
  }
}

function renderStatusActionMenu(allowedStatuses) {
  const menu = document.getElementById("statusActionMenu");
  const updateBtn = document.getElementById("updateStatusBtn");

  if (!menu || !updateBtn) return;

  if (!allowedStatuses || allowedStatuses.length === 0) {
    menu.innerHTML = `
      <li>
        <span class="dropdown-item text-muted">No further status updates available</span>
      </li>
    `;
    updateBtn.disabled = true;
    return;
  }

  menu.innerHTML = allowedStatuses
    .map(
      (status) => `
        <li>
          <button class="dropdown-item fw-bold"
                  type="button"
                  onclick="openStatusConfirmModal('${status.value}', '${status.label}')">
            ${getStatusActionText(status.value, status.label)}
          </button>
        </li>
      `,
    )
    .join("");

  updateBtn.disabled = false;
}
// 1. Evaluates ID, Name, Dates, Checkboxes, AND Pagination
function applyAllFilters(resetPage = true, resetDetails = true) {
  if (resetPage) {
    currentPage = 1;
  }

  // Get text/date filter values
  const orderIdSearch = document
    .getElementById("filterOrderId")
    .value.toLowerCase();
  const nameSearch = document
    .getElementById("filterCustomerName")
    .value.toLowerCase();
  const fromDate = document.getElementById("filterDateFrom").value;
  const toDate = document.getElementById("filterDateTo").value;

  // Gather an array of all the status codes that are currently checked
  const checkedStatuses = Array.from(
    document.querySelectorAll(".status-filter:checked"),
  ).map((cb) => cb.value);

  let matchingRows = [];

  document.querySelectorAll(".order-row").forEach((row) => {
    // Grab the row's hidden data attributes
    const status = row.getAttribute("data-status");
    const orderId = row.getAttribute("data-order-id");
    const customerName = row.getAttribute("data-customer-name");
    const dueDate = row.getAttribute("data-due-date");

    let statusMatch = checkedStatuses.includes(status);
    let orderIdMatch = orderId.includes(orderIdSearch);
    let nameMatch = customerName.includes(nameSearch);
    let fromMatch = true;
    let toMatch = true;

    if (fromDate !== "" && dueDate < fromDate) fromMatch = false;
    if (toDate !== "" && dueDate > toDate) toMatch = false;

    // If ALL conditions are met, save it to matching array
    if (statusMatch && orderIdMatch && nameMatch && fromMatch && toMatch) {
      matchingRows.push(row);
    } else {
      row.style.display = "none"; // Hide immediately if it fails the filter
    }
  });

  // --- PAGINATION LOGIC ---
  const totalRows = matchingRows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

  if (currentPage > totalPages) {
    currentPage = totalPages;
  }

  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;

  matchingRows.forEach((row, index) => {
    if (index >= startIndex && index < endIndex) {
      row.style.display = "";
    } else {
      row.style.display = "none";
    }
  });

  const emptyRow = document.getElementById("emptyStateRow");
  if (emptyRow) {
    emptyRow.style.display = totalRows === 0 ? "" : "none";
  }

  renderPagination(totalPages);

  // --- RESET DETAILS PANEL ---
  if (resetDetails) {
    selectedSummaryId = null;
    document
      .querySelectorAll(".order-row")
      .forEach((r) => r.classList.remove("selected"));
    document
      .querySelectorAll(".sub-row")
      .forEach((r) => r.classList.remove("selected"));

    const detailOrderId = document.getElementById("detailOrderId");
    const detailsContent = document.getElementById("detailsContent");

    if (detailOrderId) detailOrderId.textContent = "Select an order";
    if (detailsContent) {
      detailsContent.innerHTML = `
    <p class="text-muted mb-3">
      Click on a specific order or subscription from the tables above to view complete details.
    </p>

    <div class="producer-help-box">
      <h6 class="fw-bold mb-2">How to use this page</h6>

      <p class="mb-2">
        This page shows orders that need action from this producer only.
        Click an order row to see customer details, products, delivery or collection information, and the next available status update.
      </p>

      <ol class="mb-0 ps-3">
        <li>Use <strong>Filter</strong> to find orders by status, order ID, customer name, or due date.</li>
        <li>Click one order row to open its full details.</li>
        <li>Use <strong>Change Status</strong> only when the order has really moved to the next stage.</li>
        <li>A confirmation box will appear before the status is saved.</li>
        <li>Status cannot be moved backwards. If a mistake is made, contact an admin.</li>
      </ol>
    </div>
  `;
    }

    const updateBtn = document.getElementById("updateStatusBtn");
    if (updateBtn) updateBtn.disabled = true;

    const statusActionMenu = document.getElementById("statusActionMenu");
    if (statusActionMenu) {
      statusActionMenu.innerHTML = `
    <li>
      <span class="dropdown-item text-muted">Select an order first</span>
    </li>
  `;
    }
  }
}

// 2. Render Pagination Buttons visually
function renderPagination(totalPages) {
  const container = document.getElementById("paginationContainer");
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = '<ul class="pagination mb-0 shadow-sm">';

  html += `<li class="page-item ${currentPage === 1 ? "disabled" : ""}">
                <button class="page-link" onclick="goToPage(${currentPage - 1})" style="color: var(--brand);">Previous</button>
             </li>`;

  for (let i = 1; i <= totalPages; i++) {
    const activeClass = currentPage === i ? "active" : "";
    const activeStyle =
      currentPage === i
        ? "background-color: #3a4b53; border-color: #3a4b53; color: #fff;"
        : "color: var(--brand);";

    html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="goToPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
  }

  html += `<li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
                <button class="page-link" onclick="goToPage(${currentPage + 1})" style="color: var(--brand);">Next</button>
             </li>`;

  html += "</ul>";
  container.innerHTML = html;
}

// 3. Jump to a new page
function goToPage(pageNumber) {
  currentPage = pageNumber;
  applyAllFilters(false);
}

// 4. Clear all filters and reset view
function clearFilters() {
  document.getElementById("filterOrderId").value = "";
  document.getElementById("filterCustomerName").value = "";
  document.getElementById("filterDateFrom").value = "";
  document.getElementById("filterDateTo").value = "";

  const defaults = {
    filterPen: true,
    filterPre: true,
    filterPac: true,
    filterRfc: true,
    filterShp: true,
    filterCom: false,
    filterCan: true,
  };

  Object.entries(defaults).forEach(([id, checked]) => {
    const input = document.getElementById(id);
    if (input) input.checked = checked;
  });

  applyAllFilters(true);
}

// 5. Highlight row and show details
function showOrderDetails(summaryId, rowElement) {
  selectedSummaryId = summaryId;

  document
    .querySelectorAll(".order-row")
    .forEach((row) => row.classList.remove("selected"));
  document
    .querySelectorAll(".sub-row")
    .forEach((row) => row.classList.remove("selected"));
  rowElement.classList.add("selected");

  const orderRef = rowElement.cells[0].innerText.split("\n")[0].trim();
  document.getElementById("detailOrderId").textContent = `Order ${orderRef}`;

  const templateContent = document.getElementById(
    `details-template-${summaryId}`,
  ).innerHTML;
  document.getElementById("detailsContent").innerHTML = templateContent;

  renderStatusActionMenu(parseAllowedStatuses(rowElement));
}

function getStatusFilterId(statusCode) {
  return (
    {
      PEN: "filterPen",
      PRE: "filterPre",
      PAC: "filterPac",
      RFC: "filterRfc",
      SHP: "filterShp",
      COM: "filterCom",
      CAN: "filterCan",
    }[statusCode] || null
  );
}

function ensureStatusFilterChecked(statusCode) {
  const filterId = getStatusFilterId(statusCode);

  if (!filterId) {
    return;
  }

  const input = document.getElementById(filterId);

  if (input) {
    input.checked = true;
  }
}

function getCurrentOrderFilterValues() {
  return {
    orderIdSearch: document.getElementById("filterOrderId").value.toLowerCase(),
    nameSearch: document
      .getElementById("filterCustomerName")
      .value.toLowerCase(),
    fromDate: document.getElementById("filterDateFrom").value,
    toDate: document.getElementById("filterDateTo").value,
    checkedStatuses: Array.from(
      document.querySelectorAll(".status-filter:checked"),
    ).map((cb) => cb.value),
  };
}

function rowMatchesCurrentOrderFilters(row) {
  const filters = getCurrentOrderFilterValues();

  const status = row.getAttribute("data-status");
  const orderId = row.getAttribute("data-order-id") || "";
  const customerName = row.getAttribute("data-customer-name") || "";
  const dueDate = row.getAttribute("data-due-date") || "";

  if (!filters.checkedStatuses.includes(status)) {
    return false;
  }

  if (!orderId.includes(filters.orderIdSearch)) {
    return false;
  }

  if (!customerName.includes(filters.nameSearch)) {
    return false;
  }

  if (filters.fromDate !== "" && dueDate < filters.fromDate) {
    return false;
  }

  if (filters.toDate !== "" && dueDate > filters.toDate) {
    return false;
  }

  return true;
}

function getMatchingOrderRowsForCurrentFilters() {
  return Array.from(document.querySelectorAll(".order-row")).filter(
    rowMatchesCurrentOrderFilters,
  );
}

function moveToPageContainingSummary(summaryId) {
  const row = document.getElementById(`row-${summaryId}`);

  if (!row) {
    return false;
  }

  const matchingRows = getMatchingOrderRowsForCurrentFilters();
  const rowIndex = matchingRows.indexOf(row);

  if (rowIndex === -1) {
    return false;
  }

  currentPage = Math.floor(rowIndex / rowsPerPage) + 1;
  return true;
}

function getDetailsCardElement() {
  return (
    document.getElementById("producerDetailsCard") ||
    document.querySelector(".details-card")
  );
}

function openSummaryDetails(summaryId, scrollToDetails = false) {
  if (!summaryId) {
    return false;
  }

  const row = document.getElementById(`row-${summaryId}`);

  if (!row) {
    return false;
  }

  const rowStatus = row.getAttribute("data-status");

  ensureStatusFilterChecked(rowStatus);
  moveToPageContainingSummary(summaryId);
  applyAllFilters(false, false);
  showOrderDetails(summaryId, row);

  if (scrollToDetails) {
    const detailsCard = getDetailsCardElement();

    if (detailsCard) {
      detailsCard.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }

  return true;
}

function reloadAndReopenSummary(summaryId) {
  if (!summaryId) {
    window.location.reload();
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.set("open_order", summaryId);
  url.searchParams.set("producer_page", String(currentPage));
  url.hash = "producerDetailsCard";

  window.location.assign(url.toString());
}

// 6. Show Subscription Details
function showSubscriptionDetails(subId, rowElement) {
  selectedSummaryId = null;

  document
    .querySelectorAll(".order-row")
    .forEach((row) => row.classList.remove("selected"));
  document
    .querySelectorAll(".sub-row")
    .forEach((row) => row.classList.remove("selected"));
  rowElement.classList.add("selected");

  document.getElementById("detailOrderId").textContent =
    `Subscription #SUB-${subId}`;

  const template = document.getElementById(`sub-details-template-${subId}`);
  if (template) {
    document.getElementById("detailsContent").innerHTML = template.innerHTML;
  }

  const updateBtn = document.getElementById("updateStatusBtn");
  if (updateBtn) updateBtn.disabled = true;
}
function getStatusActionText(statusValue, fallbackLabel) {
  const actionText = {
    PRE: "Start preparing",
    PAC: "Items are packed",
    RFC: "Ready for customer collection",
    SHP: "Order has been shipped",
    COM: "Order is completed",
  };

  return actionText[statusValue] || `Mark as ${fallbackLabel}`;
}

function openStatusConfirmModal(statusValue, statusLabel) {
  pendingStatusValue = statusValue;
  pendingStatusLabel = statusLabel;

  const statusName = document.getElementById("confirmStatusName");
  const statusHelp = document.getElementById("confirmStatusHelp");

  if (statusName) {
    statusName.textContent = statusLabel;
  }

  if (statusHelp) {
    statusHelp.textContent =
      STATUS_CONFIRMATION_HELP[statusValue] ||
      "Only continue if this status is correct.";
  }

  const modalElement = document.getElementById("statusConfirmModal");
  if (!modalElement) return;

  const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
  modal.show();
}

function closeStatusConfirmModal() {
  const modalElement = document.getElementById("statusConfirmModal");
  if (!modalElement) return;

  const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
  modal.hide();
}

// 7. Send AJAX update with the newly selected status
async function changeStatus(newStatus) {
  if (!selectedSummaryId) return;

  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  if (!csrfInput) {
    alert("CSRF token not found.");
    return;
  }

  try {
    const response = await fetch(
      `/accounts/update-order-status/${selectedSummaryId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfInput.value,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: newStatus }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      alert(data.error || "Something went wrong updating the order.");
      return;
    }

    reloadAndReopenSummary(selectedSummaryId);
    return;
  } catch (error) {
    console.error("Error updating status:", error);
    alert("Network error occurred.");
  }
}

// 8. Send AJAX to Cancel Subscription
async function cancelSubscription(subId) {
  if (
    !confirm(
      "Are you sure you want to cancel this subscription?\n\nThis will stop future orders from generating and cancel any existing future orders (except the nearest incoming one).",
    )
  ) {
    return;
  }

  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  if (!csrfInput) return;

  try {
    const response = await fetch(`/accounts/cancel-subscription/${subId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfInput.value,
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      alert("Subscription cancelled successfully.");
      // Reload the page to refresh the active subscriptions and cancelled orders table
      window.location.reload();
    } else {
      alert("Something went wrong cancelling the subscription.");
    }
  } catch (error) {
    console.error("Error cancelling subscription:", error);
    alert("Network error occurred.");
  }
}

// 9. Subscription table filtering + pagination
function applySubFilters(resetPage = true) {
  if (resetPage) subCurrentPage = 1;

  const checkedStatuses = Array.from(
    document.querySelectorAll(".sub-status-filter:checked"),
  ).map((cb) => cb.value);

  let matchingRows = [];

  document.querySelectorAll(".sub-row").forEach((row) => {
    const status = row.getAttribute("data-sub-status");
    if (checkedStatuses.includes(status)) {
      matchingRows.push(row);
    } else {
      row.style.display = "none";
    }
  });

  // Pagination
  const totalRows = matchingRows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

  if (subCurrentPage > totalPages) subCurrentPage = totalPages;

  const startIndex = (subCurrentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;

  matchingRows.forEach((row, index) => {
    row.style.display = index >= startIndex && index < endIndex ? "" : "none";
  });

  renderSubPagination(totalPages);
}

function renderSubPagination(totalPages) {
  const container = document.getElementById("subPaginationContainer");
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = '<ul class="pagination mb-0 shadow-sm">';

  html += `<li class="page-item ${subCurrentPage === 1 ? "disabled" : ""}">
                <button class="page-link" onclick="goToSubPage(${subCurrentPage - 1})" style="color: var(--brand);">Previous</button>
             </li>`;

  for (let i = 1; i <= totalPages; i++) {
    const activeClass = subCurrentPage === i ? "active" : "";
    const activeStyle =
      subCurrentPage === i
        ? "background-color: #3a4b53; border-color: #3a4b53; color: #fff;"
        : "color: var(--brand);";
    html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="goToSubPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
  }

  html += `<li class="page-item ${subCurrentPage === totalPages ? "disabled" : ""}">
                <button class="page-link" onclick="goToSubPage(${subCurrentPage + 1})" style="color: var(--brand);">Next</button>
             </li>`;

  html += "</ul>";
  container.innerHTML = html;
}

function goToSubPage(pageNumber) {
  subCurrentPage = pageNumber;
  applySubFilters(false);
}

function clearSubFilters() {
  document.getElementById("subFilterActive").checked = true;
  document.getElementById("subFilterPaused").checked = true;
  document.getElementById("subFilterCancelled").checked = false;
  applySubFilters(true);
}

// 10. Pause / Resume Subscription
async function toggleSubscription(subId) {
  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  if (!csrfInput) return;

  try {
    const response = await fetch(`/accounts/toggle-subscription/${subId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfInput.value,
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      const row = document.getElementById(`sub-row-${subId}`);
      if (row) {
        row.setAttribute("data-sub-status", data.new_status);

        const badge = row.querySelector(".sub-status-badge");
        if (badge) {
          badge.textContent = data.new_status_display;
          badge.className = "status-badge sub-status-badge";
          if (data.new_status === "ACTIVE")
            badge.classList.add("status-packaged");
          else if (data.new_status === "PAUSED")
            badge.classList.add("status-pending");
          else badge.classList.add("status-cancelled");
        }
      }
      // Reload to refresh the details template buttons
      window.location.reload();
    } else {
      alert("Something went wrong toggling the subscription.");
    }
  } catch (error) {
    console.error("Error toggling subscription:", error);
    alert("Network error occurred.");
  }
}

async function cancelProducerOrder(summaryId) {
  const reason = prompt(
    "Please enter the reason for cancelling this producer order.\n\nThis will cancel this producer section and refund the customer.",
  );

  if (reason === null) {
    return;
  }

  const cleanReason = reason.trim();

  if (!cleanReason) {
    alert("A cancellation reason is required.");
    return;
  }

  const confirmCancel = confirm(
    "Are you sure you want to cancel this producer order?\n\nThe customer will be refunded for this producer section. This cannot be undone.",
  );

  if (!confirmCancel) {
    return;
  }

  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");

  if (!csrfInput) {
    alert("CSRF token not found.");
    return;
  }

  try {
    const response = await fetch(
      `/accounts/cancel-producer-order/${summaryId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfInput.value,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: cleanReason }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      alert(
        data.error || "Something went wrong cancelling the producer order.",
      );
      return;
    }

    alert(
      "Producer order cancelled successfully. Refund result: " +
        (data.refund?.message || "Processed."),
    );

    reloadAndReopenSummary(summaryId);
  } catch (error) {
    console.error("Error cancelling producer order:", error);
    alert("Network error occurred.");
  }
}

async function cancelProducerOrderItem(itemId, productName, summaryId = null) {
  const quantityInput = prompt(
    `How many ${productName} item(s) need to be cancelled?\n\nExample: if 2 out of 3 expired, enter 2.`,
  );

  if (quantityInput === null) {
    return;
  }

  const quantityToCancel = Number.parseInt(quantityInput.trim(), 10);

  if (!Number.isInteger(quantityToCancel) || quantityToCancel <= 0) {
    alert("Please enter a valid whole number greater than 0.");
    return;
  }

  const reason = prompt(
    `Please enter the reason for cancelling ${quantityToCancel} of ${productName}.\n\nExample: 2 expired after stock check.`,
  );

  if (reason === null) {
    return;
  }

  const cleanReason = reason.trim();

  if (!cleanReason) {
    alert("A cancellation reason is required.");
    return;
  }

  const confirmCancel = confirm(
    `Are you sure you want to cancel ${quantityToCancel} of ${productName}?\n\nThe customer will be refunded for this cancelled quantity only. This cannot be undone.`,
  );

  if (!confirmCancel) {
    return;
  }

  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");

  if (!csrfInput) {
    alert("CSRF token not found.");
    return;
  }

  try {
    const response = await fetch(
      `/accounts/cancel-producer-order-item/${itemId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfInput.value,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          reason: cleanReason,
          quantity_to_cancel: quantityToCancel,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      alert(data.error || "Something went wrong cancelling this item.");
      return;
    }

    alert(
      `Cancelled quantity: ${data.cancelled_quantity || quantityToCancel}\n` +
        "Refund result: " +
        (data.refund?.message || "Processed."),
    );

    reloadAndReopenSummary(summaryId || selectedSummaryId);
  } catch (error) {
    console.error("Error cancelling producer order item:", error);
    alert("Network error occurred.");
  }
}
// 11. Initialize when the DOM loads
document.addEventListener("DOMContentLoaded", () => {
  const resetAndFilter = () => applyAllFilters(true);

  document
    .getElementById("filterOrderId")
    .addEventListener("input", resetAndFilter);

  document
    .getElementById("filterCustomerName")
    .addEventListener("input", resetAndFilter);

  document
    .getElementById("filterDateFrom")
    .addEventListener("change", resetAndFilter);

  document
    .getElementById("filterDateTo")
    .addEventListener("change", resetAndFilter);

  document.querySelectorAll(".status-filter").forEach((cb) => {
    cb.addEventListener("change", resetAndFilter);
  });

  document.querySelectorAll(".sub-status-filter").forEach((cb) => {
    cb.addEventListener("change", () => applySubFilters(true));
  });

  const params = new URLSearchParams(window.location.search);
  const openOrderId = params.get("open_order");
  const savedProducerPage = Number(params.get("producer_page"));

  if (Number.isFinite(savedProducerPage) && savedProducerPage > 0) {
    currentPage = savedProducerPage;
  }

  applyAllFilters(false);
  applySubFilters(true);

  const confirmStatusUpdateBtn = document.getElementById(
    "confirmStatusUpdateBtn",
  );

  if (confirmStatusUpdateBtn) {
    confirmStatusUpdateBtn.addEventListener("click", async () => {
      if (!pendingStatusValue) return;

      confirmStatusUpdateBtn.disabled = true;
      confirmStatusUpdateBtn.textContent = "Updating...";

      await changeStatus(pendingStatusValue);

      confirmStatusUpdateBtn.disabled = false;
      confirmStatusUpdateBtn.textContent = "Confirm update";

      pendingStatusValue = null;
      pendingStatusLabel = null;

      closeStatusConfirmModal();
    });
  }

  if (openOrderId) {
    setTimeout(() => {
      openSummaryDetails(openOrderId, true);
    }, 80);
  }
});
