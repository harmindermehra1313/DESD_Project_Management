const ORDER_HISTORY_API_URL = "/api/order-history/history/";
const ORDER_DETAIL_API_BASE = "/api/order-history/";
const ORDER_REORDER_API_SUFFIX = "/reorder/";
const RECEIPT_URL_BASE = "/orders/receipt/";

const DEFAULT_FILTERS = {
  status: "",
  start_date: "",
  end_date: "",
  delivery_or_collection: "",
  recurring_only: "",
};

let appliedFilters = { ...DEFAULT_FILTERS };

let currentPage = 1;
let totalCount = 0;
let pageSize = 10;

let detailModal;
let reorderModal;

document.addEventListener("DOMContentLoaded", () => {
  const detailModalElement = document.getElementById("orderDetailModal");
  const reorderModalElement = document.getElementById("reorderResultModal");

  if (detailModalElement) {
    detailModal = new bootstrap.Modal(detailModalElement);
  }

  if (reorderModalElement) {
    reorderModal = new bootstrap.Modal(reorderModalElement);
  }

  appliedFilters = readFiltersFromForm();
  bindEvents();
  loadOrders();
});

function readFiltersFromForm() {
  return {
    status: document.getElementById("status")?.value?.trim() || "",
    start_date: document.getElementById("start_date")?.value || "",
    end_date: document.getElementById("end_date")?.value || "",
    delivery_or_collection: document.getElementById("delivery_or_collection")?.value || "",
    recurring_only: document.getElementById("recurring_only")?.value || "",
  };
}

function writeFiltersToForm(filters) {
  const statusEl = document.getElementById("status");
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");
  const fulfilmentEl = document.getElementById("delivery_or_collection");
  const recurringEl = document.getElementById("recurring_only");

  if (statusEl) statusEl.value = filters.status || "";
  if (startDateEl) startDateEl.value = filters.start_date || "";
  if (endDateEl) endDateEl.value = filters.end_date || "";
  if (fulfilmentEl) fulfilmentEl.value = filters.delivery_or_collection || "";
  if (recurringEl) recurringEl.value = filters.recurring_only || "";
}
function getTodayDateString() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function clearDateValidationState() {
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");
  const errorBox = document.getElementById("orderListError");

  [startDateEl, endDateEl].forEach((el) => {
    if (!el) return;
    el.classList.remove("is-invalid");
    el.setCustomValidity("");
  });

  if (errorBox) {
    errorBox.classList.add("d-none");
    errorBox.textContent = "";
  }
}

function showDateValidationError(message, fields = []) {
  const errorBox = document.getElementById("orderListError");

  fields.forEach((field) => {
    field?.classList.add("is-invalid");
    field?.setCustomValidity(message);
  });

  if (errorBox) {
    errorBox.textContent = message;
    errorBox.classList.remove("d-none");
  }
}

function validateDateFilters() {
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");

  if (!startDateEl || !endDateEl) {
    return true;
  }

  clearDateValidationState();

  const startDate = startDateEl.value;
  const endDate = endDateEl.value;
  const today = getTodayDateString();

  if (startDate && startDate > today) {
    showDateValidationError("Start date cannot be in the future.", [startDateEl]);
    return false;
  }

  if (endDate && endDate > today) {
    showDateValidationError("End date cannot be in the future.", [endDateEl]);
    return false;
  }

  if (startDate && endDate && startDate > endDate) {
    showDateValidationError("Start date must be earlier than or equal to end date.", [
      startDateEl,
      endDateEl,
    ]);
    return false;
  }

  return true;
}

function applyDateInputLimits() {
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");
  const today = getTodayDateString();

  if (startDateEl) {
    startDateEl.max = today;
  }

  if (endDateEl) {
    endDateEl.max = today;
  }
}

function resetAppliedFilters() {
  appliedFilters = { ...DEFAULT_FILTERS };
}

function bindEvents() {
  const filtersForm = document.getElementById("orderFiltersForm");
  const resetBtn = document.getElementById("resetFiltersBtn");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");

  applyDateInputLimits();

  if (filtersForm) {
    filtersForm.addEventListener("submit", (event) => {
      event.preventDefault();

      if (!validateDateFilters()) {
        return;
      }

      appliedFilters = readFiltersFromForm();
      currentPage = 1;
      loadOrders();
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      resetAppliedFilters();
      writeFiltersToForm(appliedFilters);
      clearDateValidationState();
      applyDateInputLimits();
      currentPage = 1;
      loadOrders();
    });
  }

  if (startDateEl) {
    startDateEl.addEventListener("change", () => {
      validateDateFilters();
    });
  }

  if (endDateEl) {
    endDateEl.addEventListener("change", () => {
      validateDateFilters();
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage -= 1;
        loadOrders();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
      if (currentPage < totalPages) {
        currentPage += 1;
        loadOrders();
      }
    });
  }
}

function buildQueryString() {
  const params = new URLSearchParams();

  if (appliedFilters.status) {
    params.append("status", appliedFilters.status);
  }

  if (appliedFilters.start_date) {
    params.append("start_date", appliedFilters.start_date);
  }

  if (appliedFilters.end_date) {
    params.append("end_date", appliedFilters.end_date);
  }

  if (appliedFilters.delivery_or_collection) {
    params.append("delivery_or_collection", appliedFilters.delivery_or_collection);
  }

  if (appliedFilters.recurring_only) {
    params.append("recurring_only", appliedFilters.recurring_only);
  }

  params.append("page", String(currentPage));
  params.append("page_size", String(pageSize));

  return params.toString();
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";

  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(dateString) {
  if (!dateString) return "-";

  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatMoney(value) {
  const amount = Number(value || 0);

  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(amount);
}

function normaliseStatus(status) {
  return (status || "").toLowerCase().trim();
}

function getStatusBadgeClass(status) {
  const value = normaliseStatus(status);

  if (value.includes("completed")) return "bg-success";
  if (value.includes("confirmed")) return "bg-info text-dark";
  if (value.includes("pending")) return "bg-warning text-dark";
  if (value.includes("cancel")) return "bg-danger";

  return "bg-secondary";
}

function isReorderAllowed(status) {
  const value = normaliseStatus(status);
  return !value.includes("pending") && !value.includes("cancel") && !value.includes("ready for collection");
}

function getReorderButtonHtml(orderId, status, extraClass = "") {
  const allowed = isReorderAllowed(status);
  const disabledAttr = allowed ? "" : "disabled";
  const title = allowed
    ? "Reorder"
    : "Reorder is not available for pending or cancelled orders";

  return `
    <button
      type="button"
      class="btn btn-dark ${extraClass}".trim()
      onclick="reorderOrder(${orderId})"
      ${disabledAttr}
      title="${escapeHtml(title)}"
    >
      Reorder
    </button>
  `;
}

function getFulfilmentType(summary) {
  return (summary?.delivery_or_collection || "").trim();
}

function isDelivery(summary) {
  return getFulfilmentType(summary).toLowerCase().includes("delivery");
}

function isCollection(summary) {
  return getFulfilmentType(summary).toLowerCase().includes("collection");
}

function getFulfilmentDate(summary) {
  if (isDelivery(summary)) return summary.delivery_date || null;
  if (isCollection(summary)) return summary.collection_date || null;
  return null;
}

function getFulfilmentSlot(summary) {
  if (isDelivery(summary)) return summary.delivery_time_slot || null;
  if (isCollection(summary)) return summary.collection_time_slot || null;
  return null;
}

function getFulfilmentAddress(summary) {
  if (isDelivery(summary)) return summary.delivery_address || null;
  if (isCollection(summary)) return summary.collection_address || null;
  return null;
}

function formatAddress(address) {
  if (!address) {
    return `<div class="text-muted">Address not available</div>`;
  }

  const lines = [
    address.line_1,
    address.line_2,
    [address.city, address.postcode].filter(Boolean).join(" "),
  ].filter(Boolean);

  if (!lines.length) {
    return `<div class="text-muted">Address not available</div>`;
  }

  return lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

function setLoadingState() {
  document.getElementById("orderListLoading")?.classList.remove("d-none");
  document.getElementById("orderListError")?.classList.add("d-none");
  document.getElementById("orderListEmpty")?.classList.add("d-none");
  document.getElementById("orderTableWrapper")?.classList.add("d-none");

  const tbody = document.getElementById("orderTableBody");
  if (tbody) {
    tbody.innerHTML = "";
  }
}

function setPaginationState(totalPages) {
  const paginationInfo = document.getElementById("paginationInfo");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");

  if (paginationInfo) {
    paginationInfo.textContent = `Page ${currentPage} of ${totalPages} · ${totalCount} total orders`;
  }

  if (prevBtn) {
    prevBtn.disabled = currentPage <= 1;
  }

  if (nextBtn) {
    nextBtn.disabled = currentPage >= totalPages;
  }
}

function setEmptyState() {
  document.getElementById("orderListLoading")?.classList.add("d-none");
  document.getElementById("orderListEmpty")?.classList.remove("d-none");

  const paginationInfo = document.getElementById("paginationInfo");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");

  if (paginationInfo) {
    paginationInfo.textContent = totalCount === 0 ? "0 orders" : `Page ${currentPage}`;
  }

  if (prevBtn) prevBtn.disabled = true;
  if (nextBtn) nextBtn.disabled = true;
}

function setErrorState(message) {
  document.getElementById("orderListLoading")?.classList.add("d-none");

  const errorBox = document.getElementById("orderListError");
  if (errorBox) {
    errorBox.textContent = message || "Failed to load orders.";
    errorBox.classList.remove("d-none");
  }
}

function renderOrdersTable(orders) {
  const wrapper = document.getElementById("orderTableWrapper");
  const tbody = document.getElementById("orderTableBody");

  if (!tbody || !wrapper) return;

  tbody.innerHTML = orders.map((order) => `
    <tr>
      <td><strong>${escapeHtml(order.order_number)}</strong></td>
      <td>${formatDate(order.order_date)}</td>
      <td>
        ${(order.producer_names || []).map((name) => `
          <span class="badge rounded-pill text-bg-light border me-1 mb-1">
            ${escapeHtml(name)}
          </span>
        `).join("")}
      </td>
      <td>${formatMoney(order.total)}</td>
      <td>
        <span class="badge ${getStatusBadgeClass(order.order_status)}">
          ${escapeHtml(order.order_status)}
        </span>
      </td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-outline-dark me-2"
          onclick="openOrderDetails(${order.id})"
        >
          View Details
        </button>
        ${getReorderButtonHtml(order.id, order.order_status, "btn-sm")}
      </td>
    </tr>
  `).join("");

  document.getElementById("orderListLoading")?.classList.add("d-none");
  wrapper.classList.remove("d-none");
}

async function parseErrorMessage(response, fallbackMessage) {
  let message = fallbackMessage;

  try {
    const errorData = await response.json();
    message =
      errorData.detail ||
      errorData.message ||
      errorData.error ||
      JSON.stringify(errorData);
  } catch (_) {
    // keep fallback
  }

  return message;
}

async function loadOrders() {
  setLoadingState();

  try {
    const response = await fetch(`${ORDER_HISTORY_API_URL}?${buildQueryString()}`, {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to load order history (${response.status})`,
      );
      throw new Error(message);
    }

    const data = await response.json();

    totalCount = Number(data.count || 0);
    const orders = Array.isArray(data.results) ? data.results : [];
    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

    if (currentPage > totalPages) {
      currentPage = 1;
      return loadOrders();
    }

    if (!orders.length) {
      setEmptyState();
      return;
    }

    renderOrdersTable(orders);
    setPaginationState(totalPages);
  } catch (error) {
    setErrorState(error.message || "Failed to load orders.");
  }
}

function buildFulfilmentGroups(producerBreakdown) {
  return (producerBreakdown || []).map((summary) => ({
    producerName: summary.producer_name || "Unknown producer",
    fulfilmentType: getFulfilmentType(summary) || "Not specified",
    date: getFulfilmentDate(summary),
    slot: getFulfilmentSlot(summary),
    address: getFulfilmentAddress(summary),
    status: summary.status || "-",
  }));
}

function renderFulfilmentSection(producerBreakdown) {
  const groups = buildFulfilmentGroups(producerBreakdown);

  if (!groups.length) {
    return `
      <div class="mb-4">
        <h6 class="mb-3">Delivery / Collection Details</h6>
        <div class="border rounded p-3">
          <div class="text-muted">Fulfilment information is not available.</div>
        </div>
      </div>
    `;
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">Delivery / Collection Details</h6>
      <div class="row g-3">
        ${groups.map((group) => `
          <div class="col-12">
            <div class="border rounded p-3">
              <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                <div>
                  <div class="fw-semibold">${escapeHtml(group.fulfilmentType)}</div>
                  <div class="text-muted small">${escapeHtml(group.producerName)}</div>
                </div>
                <span class="badge text-bg-light border">${escapeHtml(group.status)}</span>
              </div>

              <div class="row g-3">
                <div class="col-md-4">
                  <div class="small text-muted">Date</div>
                  <div class="fw-semibold">${formatDate(group.date)}</div>
                </div>
                <div class="col-md-4">
                  <div class="small text-muted">Time slot</div>
                  <div class="fw-semibold">${escapeHtml(group.slot || "-")}</div>
                </div>
                <div class="col-md-4">
                  <div class="small text-muted">
                    ${group.fulfilmentType.toLowerCase().includes("collection")
                      ? "Collection address"
                      : "Delivery address"}
                  </div>
                  <div>${formatAddress(group.address)}</div>
                </div>
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderItemsSection(items) {
  return `
    <div class="mb-4">
      <h6 class="mb-3">Items</h6>
      <div class="table-responsive">
        <table class="table table-bordered align-middle">
          <thead class="table-light">
            <tr>
              <th>Product</th>
              <th>Producer</th>
              <th>Quantity</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            ${(items || []).map((item) => `
              <tr>
                <td>${escapeHtml(item.product_name)}</td>
                <td>${escapeHtml(item.producer)}</td>
                <td>${escapeHtml(item.quantity)}</td>
                <td>${formatMoney(item.price)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderProducerSection(producerBreakdown) {
  if (!(producerBreakdown || []).length) {
    return `
      <div class="mb-4">
        <h6 class="mb-3">Producer Details</h6>
        <div class="border rounded p-3">
          <div class="text-muted">Producer details are not available.</div>
        </div>
      </div>
    `;
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">Producer Details</h6>
      ${(producerBreakdown || []).map((summary) => `
        <div class="card mb-3">
          <div class="card-body">
            <div class="d-flex justify-content-between flex-wrap gap-2 mb-3">
              <div>
                <h6 class="mb-1">${escapeHtml(summary.producer_name)}</h6>
                <div class="text-muted small">${escapeHtml(summary.status || "-")}</div>
              </div>
              <div class="text-end">
                <div class="small text-muted">Subtotal</div>
                <div class="fw-semibold">${formatMoney(summary.subtotal)}</div>
              </div>
            </div>

            <div class="row g-3">
              <div class="col-md-3">
                <small class="text-muted">Fulfilment type</small>
                <div>${escapeHtml(summary.delivery_or_collection || "-")}</div>
              </div>
              <div class="col-md-3">
                <small class="text-muted">VAT</small>
                <div>${formatMoney(summary.vat_total)}</div>
              </div>
              <div class="col-md-6">
                <small class="text-muted">Instructions</small>
                <div>${escapeHtml(summary.special_instructions || "-")}</div>
              </div>
            </div>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderOrderSummary(order) {
  return `
    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="text-muted small">Order Number</div>
          <div class="fw-semibold">${escapeHtml(order.order_number)}</div>
        </div>
      </div>

      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="text-muted small">Order Date</div>
          <div class="fw-semibold">${formatDate(order.order_date)}</div>
        </div>
      </div>

      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="text-muted small">Status</div>
          <div class="fw-semibold">${escapeHtml(order.status)}</div>
        </div>
      </div>

      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="text-muted small">Payment</div>
          <div class="fw-semibold">${escapeHtml(order.payment_method_display || "Not available")}</div>
        </div>
      </div>
    </div>
  `;
}

function renderOrderFooter(order) {
  return `
    <div class="border rounded p-3 d-flex justify-content-between align-items-center flex-wrap gap-3">
      <div>
        <div class="small text-muted">Total Paid</div>
        <div class="fs-5 fw-bold">${formatMoney(order.total_price)}</div>
      </div>

      <div class="d-flex gap-2">
        ${getReorderButtonHtml(order.id, order.status)}
        <a
          class="btn btn-outline-secondary"
          href="${RECEIPT_URL_BASE}${order.id}/"
        >
          Download Receipt
        </a>
      </div>
    </div>
  `;
}

async function openOrderDetails(orderId) {
  const loading = document.getElementById("orderDetailLoading");
  const errorBox = document.getElementById("orderDetailError");
  const content = document.getElementById("orderDetailContent");

  loading?.classList.remove("d-none");
  errorBox?.classList.add("d-none");
  content?.classList.add("d-none");

  if (content) {
    content.innerHTML = "";
  }

  detailModal?.show();

  try {
    const response = await fetch(`${ORDER_DETAIL_API_BASE}${orderId}/`, {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to load order details (${response.status})`,
      );
      throw new Error(message);
    }

    const order = await response.json();

    if (!content) return;

    content.innerHTML = `
      ${renderOrderSummary(order)}
      ${renderFulfilmentSection(order.producer_breakdown || [])}
      ${renderItemsSection(order.items || [])}
      ${renderProducerSection(order.producer_breakdown || [])}
      ${renderOrderFooter(order)}
    `;

    loading?.classList.add("d-none");
    content.classList.remove("d-none");
  } catch (error) {
    loading?.classList.add("d-none");
    if (errorBox) {
      errorBox.textContent = error.message || "Failed to load order details.";
      errorBox.classList.remove("d-none");
    }
  }
}

async function reorderOrder(orderId) {
  try {
    const response = await fetch(`${ORDER_DETAIL_API_BASE}${orderId}${ORDER_REORDER_API_SUFFIX}`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Reorder failed (${response.status})`,
      );
      throw new Error(message);
    }

    const result = await response.json();
    renderReorderResult(result);
    reorderModal?.show();
  } catch (error) {
    alert(error.message || "Reorder failed.");
  }
}

function renderReorderResult(result) {
  const container = document.getElementById("reorderResultContent");
  if (!container) return;

  container.innerHTML = `
    <div class="alert alert-info">
      <div class="fw-semibold">${escapeHtml(result.message || "Reorder completed.")}</div>
      <div class="small mt-1">
        Added: ${(result.added_items || []).length} |
        Unavailable: ${(result.unavailable_items || []).length} |
        Quantity adjusted: ${(result.quantity_adjusted_items || []).length} |
        Price changed: ${(result.price_changed_items || []).length}
      </div>
    </div>

    <div class="mb-4">
      <h6>Added to Cart</h6>
      ${(result.added_items || []).length
        ? result.added_items.map((item) => `
          <div class="border rounded p-2 mb-2">
            <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
            <div class="small text-muted">
              Producer: ${escapeHtml(item.producer_name)} |
              Requested: ${escapeHtml(item.requested_quantity)} |
              Added: ${escapeHtml(item.added_quantity)}
            </div>
          </div>
        `).join("")
        : `<div class="text-muted">No items added.</div>`}
    </div>

    <div class="mb-4">
      <h6>Unavailable Items</h6>
      ${(result.unavailable_items || []).length
        ? result.unavailable_items.map((item) => `
          <div class="border border-danger rounded p-2 mb-2 bg-light">
            <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
            <div class="small text-danger">
              Requested: ${escapeHtml(item.requested_quantity)} |
              Reason: ${escapeHtml(item.reason)}
            </div>
          </div>
        `).join("")
        : `<div class="text-muted">No unavailable items.</div>`}
    </div>

    <div class="mb-4">
      <h6>Quantity Adjustments</h6>
      ${(result.quantity_adjusted_items || []).length
        ? result.quantity_adjusted_items.map((item) => `
          <div class="border border-warning rounded p-2 mb-2 bg-light">
            <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
            <div class="small text-warning-emphasis">
              Requested: ${escapeHtml(item.requested_quantity)} |
              Added: ${escapeHtml(item.added_quantity)} |
              ${escapeHtml(item.reason)}
            </div>
          </div>
        `).join("")
        : `<div class="text-muted">No quantity adjustments.</div>`}
    </div>

    <div>
      <h6>Price Changes</h6>
      ${(result.price_changed_items || []).length
        ? result.price_changed_items.map((item) => `
          <div class="border border-primary rounded p-2 mb-2 bg-light">
            <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
            <div class="small text-primary">
              Original: ${formatMoney(item.original_price)} |
              Current: ${formatMoney(item.current_price)}
            </div>
          </div>
        `).join("")
        : `<div class="text-muted">No price changes.</div>`}
    </div>
  `;
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