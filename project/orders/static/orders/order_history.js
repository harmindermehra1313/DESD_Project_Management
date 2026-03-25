const ORDER_HISTORY_API_URL = "/api/orders/history/";
const ORDER_DETAIL_API_BASE = "/api/orders/";
const ORDER_REORDER_PREVIEW_API_SUFFIX = "/reorder-preview/";
const ORDER_REORDER_API_SUFFIX = "/reorder/";
const RECEIPT_URL_BASE = "/orders/receipt/";

const DEFAULT_FILTERS = {
  status: "",
  start_date: "",
  end_date: "",
  delivery_or_collection: "",
  recurring_only: "",
};

const REORDER_PREVIEW_FOOTER = `
  <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
    Cancel
  </button>
  <button type="button" class="btn btn-dark" id="confirmReorderBtn">
    Confirm Reorder
  </button>
`;

const REORDER_RESULT_FOOTER = `
  <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
    Close
  </button>
  <a href="/cart/" class="btn btn-dark">Go to Cart</a>
`;

let appliedFilters = { ...DEFAULT_FILTERS };
let currentPage = 1;
let totalCount = 0;
let pageSize = 10;

let detailModal = null;
let reorderModal = null;
let pendingReorderOrderId = null;

document.addEventListener("DOMContentLoaded", () => {
  const detailModalEl = document.getElementById("orderDetailModal");
  const reorderModalEl = document.getElementById("reorderModal");

  if (detailModalEl) {
    detailModal = new bootstrap.Modal(detailModalEl);
  }

  if (reorderModalEl) {
    reorderModal = new bootstrap.Modal(reorderModalEl);
  }

  appliedFilters = readFiltersFromForm();
  bindEvents();
  applyDateInputLimits();
  loadOrders();
});

function bindEvents() {
  const filtersForm = document.getElementById("orderFiltersForm");
  const resetBtn = document.getElementById("resetFiltersBtn");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");
  const reorderModalEl = document.getElementById("reorderModal");

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
      appliedFilters = { ...DEFAULT_FILTERS };
      writeFiltersToForm(appliedFilters);
      clearDateValidationState();
      applyDateInputLimits();
      currentPage = 1;
      loadOrders();
    });
  }

  if (startDateEl) {
    startDateEl.addEventListener("change", validateDateFilters);
  }

  if (endDateEl) {
    endDateEl.addEventListener("change", validateDateFilters);
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

  document.addEventListener("click", async (event) => {
    const detailsBtn = event.target.closest("[data-action='view-details']");
    if (detailsBtn) {
      const orderId = detailsBtn.dataset.orderId;
      if (orderId) {
        await openOrderDetails(orderId);
      }
      return;
    }

    const reorderBtn = event.target.closest("[data-action='open-reorder-preview']");
    if (reorderBtn) {
      const orderId = reorderBtn.dataset.orderId;
      if (orderId) {
        await openReorderPreview(orderId);
      }
      return;
    }

    const confirmBtn = event.target.closest("#confirmReorderBtn");
    if (confirmBtn && pendingReorderOrderId) {
      await confirmReorder(pendingReorderOrderId);
    }
  });

  if (reorderModalEl) {
    reorderModalEl.addEventListener("hidden.bs.modal", () => {
      pendingReorderOrderId = null;
      resetReorderModal();
    });
  }
}

function readFiltersFromForm() {
  return {
    status: document.getElementById("status")?.value || "",
    start_date: document.getElementById("start_date")?.value || "",
    end_date: document.getElementById("end_date")?.value || "",
    delivery_or_collection: document.getElementById("delivery_or_collection")?.value || "",
    recurring_only: document.getElementById("recurring_only")?.value || "",
  };
}

function writeFiltersToForm(filters) {
  const fields = ["status", "start_date", "end_date", "delivery_or_collection", "recurring_only"];
  fields.forEach((field) => {
    const el = document.getElementById(field);
    if (el) {
      el.value = filters[field] || "";
    }
  });
}

function buildQueryString() {
  const params = new URLSearchParams();

  Object.entries(appliedFilters).forEach(([key, value]) => {
    if (value !== "") {
      params.append(key, value);
    }
  });

  params.append("page", String(currentPage));
  params.append("page_size", String(pageSize));

  return params.toString();
}

function getTodayDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const MIN_ORDER_FILTER_DATE = "2000-01-01";

function applyDateInputLimits() {
  const today = getTodayDateString();
  const startDateEl = document.getElementById("start_date");
  const endDateEl = document.getElementById("end_date");

  if (startDateEl) {
    startDateEl.min = MIN_ORDER_FILTER_DATE;
    startDateEl.max = today;
  }

  if (endDateEl) {
    endDateEl.min = MIN_ORDER_FILTER_DATE;
    endDateEl.max = today;
  }
}

function clearDateValidationState() {
  const errorBox = document.getElementById("orderListError");
  const fields = [
    document.getElementById("start_date"),
    document.getElementById("end_date"),
  ];

  fields.forEach((field) => {
    if (!field) return;
    field.classList.remove("is-invalid");
    field.setCustomValidity("");
  });

  if (errorBox) {
    errorBox.classList.add("d-none");
    errorBox.textContent = "";
  }
}

function showDateValidationError(message, fields = []) {
  const errorBox = document.getElementById("orderListError");

  fields.forEach((field) => {
    if (!field) return;
    field.classList.add("is-invalid");
    field.setCustomValidity(message);
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

  if (startDate && startDate < MIN_ORDER_FILTER_DATE) {
    showDateValidationError(
      `Start date cannot be earlier than ${MIN_ORDER_FILTER_DATE}.`,
      [startDateEl],
    );
    return false;
  }

  if (endDate && endDate < MIN_ORDER_FILTER_DATE) {
    showDateValidationError(
      `End date cannot be earlier than ${MIN_ORDER_FILTER_DATE}.`,
      [endDateEl],
    );
    return false;
  }

  if (startDate && startDate > today) {
    showDateValidationError("Start date cannot be in the future.", [startDateEl]);
    return false;
  }

  if (endDate && endDate > today) {
    showDateValidationError("End date cannot be in the future.", [endDateEl]);
    return false;
  }

  if (startDate && endDate && startDate > endDate) {
    showDateValidationError(
      "Start date must be earlier than or equal to end date.",
      [startDateEl, endDateEl],
    );
    return false;
  }

  return true;
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

function normaliseStatus(status) {
  return (status || "").trim().toLowerCase();
}

function getStatusBadgeClass(status) {
  const value = normaliseStatus(status);

  if (value.includes("completed")) return "bg-success";
  if (value.includes("pending")) return "bg-warning text-dark";
  if (value.includes("cancel")) return "bg-danger";
  if (value.includes("in progress")) return "bg-info text-dark";
  if (value.includes("out for delivery")) return "bg-primary";
  if (value.includes("ready for collection")) return "bg-secondary";

  return "bg-secondary";
}

function isReorderAllowed(status) {
  const value = normaliseStatus(status);
  return !value.includes("pending") && !value.includes("cancel");
}
function isReceiptAllowed(status) {
  const value = normaliseStatus(status);
  return value.includes("completed");
}

function getReorderButtonHtml(orderId, status, extraClass = "") {
  const allowed = isReorderAllowed(status);
  const disabledAttr = allowed ? "" : "disabled";
  const title = allowed
    ? "Preview reorder changes"
    : "Reorder is not available for pending or cancelled orders";

  return `
    <button
      type="button"
      class="btn btn-dark ${escapeHtml(extraClass)}"
      data-action="open-reorder-preview"
      data-order-id="${escapeHtml(orderId)}"
      ${disabledAttr}
      title="${escapeHtml(title)}"
    >
      Reorder
    </button>
  `;
}
function getReceiptButtonHtml(orderId, status) {
  const allowed = isReceiptAllowed(status);

  if (!allowed) {
    return `
      <button
        type="button"
        class="btn btn-outline-secondary"
        disabled
        title="Receipt is only available for completed orders"
      >
        See Receipt
      </button>
    `;
  }

  return `
    <a
      class="btn btn-outline-secondary"
      href="${RECEIPT_URL_BASE}${orderId}/"
    >
      See Receipt
    </a>
  `;
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

function setEmptyState() {
  document.getElementById("orderListLoading")?.classList.add("d-none");
  document.getElementById("orderTableWrapper")?.classList.add("d-none");
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
  document.getElementById("orderTableWrapper")?.classList.add("d-none");

  const errorBox = document.getElementById("orderListError");
  if (errorBox) {
    errorBox.textContent = message || "Failed to load orders.";
    errorBox.classList.remove("d-none");
  }
}

function setPaginationState(totalPages) {
  const paginationInfo = document.getElementById("paginationInfo");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");

  if (paginationInfo) {
    paginationInfo.textContent = `Page ${currentPage} of ${totalPages} · ${totalCount} total orders`;
  }

  if (prevBtn) prevBtn.disabled = currentPage <= 1;
  if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
}

async function parseErrorMessage(response, fallbackMessage) {
  try {
    const data = await response.json();
    return data.detail || data.message || data.error || JSON.stringify(data);
  } catch (_) {
    return fallbackMessage;
  }
}

async function loadOrders() {
  setLoadingState();

  try {
    const response = await fetch(`${ORDER_HISTORY_API_URL}?${buildQueryString()}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
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

function renderOrdersTable(orders) {
  const wrapper = document.getElementById("orderTableWrapper");
  const tbody = document.getElementById("orderTableBody");

  if (!wrapper || !tbody) return;

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
          data-action="view-details"
          data-order-id="${escapeHtml(order.id)}"
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

function renderOrderSummary(order) {
  return `
    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Order Number</div>
          <div class="fw-semibold">${escapeHtml(order.order_number)}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Order Date</div>
          <div class="fw-semibold">${formatDate(order.order_date)}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Status</div>
          <div class="fw-semibold">${escapeHtml(order.status || order.order_status || "-")}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Payment</div>
          <div class="fw-semibold">${escapeHtml(order.payment_method_display || "Not available")}</div>
        </div>
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
              <th>Unit Price</th>
            </tr>
          </thead>
          <tbody>
            ${(items || []).map((item) => `
              <tr>
                <td>${escapeHtml(item.product_name)}</td>
                <td>${escapeHtml(item.producer)}</td>
                <td>${escapeHtml(item.quantity)}</td>
                <td>${formatMoney(item.paid_unit_price)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderFulfilmentSection(producerBreakdown) {
  if (!(producerBreakdown || []).length) {
    return `
      <div class="mb-4">
        <h6 class="mb-3">Delivery / Collection Details</h6>
        <div class="border rounded p-3 text-muted">
          Fulfilment information is not available.
        </div>
      </div>
    `;
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">Delivery / Collection Details</h6>
      <div class="row g-3">
        ${(producerBreakdown || []).map((summary) => {
          const isCollection = (summary.delivery_or_collection || "").toLowerCase().includes("collection");
          const date = isCollection ? summary.collection_date : summary.delivery_date;
          const timeSlot = isCollection ? summary.collection_time_slot : summary.delivery_time_slot;
          const address = isCollection ? summary.collection_address : summary.delivery_address;
          const addressLabel = isCollection ? "Collection address" : "Delivery address";

          return `
            <div class="col-12">
              <div class="border rounded p-3">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                  <div>
                    <div class="fw-semibold">${escapeHtml(summary.delivery_or_collection || "-")}</div>
                    <div class="small text-muted">${escapeHtml(summary.producer_name || "Unknown producer")}</div>
                  </div>
                  <span class="badge text-bg-light border">${escapeHtml(summary.status || "-")}</span>
                </div>

                <div class="row g-3">
                  <div class="col-md-4">
                    <div class="small text-muted">Date</div>
                    <div class="fw-semibold">${formatDate(date)}</div>
                  </div>
                  <div class="col-md-4">
                    <div class="small text-muted">Time slot</div>
                    <div class="fw-semibold">${escapeHtml(timeSlot || "-")}</div>
                  </div>
                  <div class="col-md-4">
                    <div class="small text-muted">${escapeHtml(addressLabel)}</div>
                    <div>${formatAddress(address)}</div>
                  </div>
                </div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderProducerSection(producerBreakdown) {
  if (!(producerBreakdown || []).length) {
    return `
      <div class="mb-4">
        <h6 class="mb-3">Producer Details</h6>
        <div class="border rounded p-3 text-muted">Producer details are not available.</div>
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
                <h6 class="mb-1">${escapeHtml(summary.producer_name || "Unknown producer")}</h6>
                <div class="small text-muted">${escapeHtml(summary.status || "-")}</div>
              </div>
              <div class="text-end">
                <div class="small text-muted">Subtotal</div>
                <div class="fw-semibold">${formatMoney(summary.subtotal)}</div>
              </div>
            </div>

            <div class="row g-3">
              <div class="col-md-3">
                <div class="small text-muted">Fulfilment type</div>
                <div>${escapeHtml(summary.delivery_or_collection || "-")}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">VAT</div>
                <div>${formatMoney(summary.vat_total)}</div>
              </div>
              <div class="col-md-6">
                <div class="small text-muted">Instructions</div>
                <div>${escapeHtml(summary.special_instructions || "-")}</div>
              </div>
            </div>
          </div>
        </div>
      `).join("")}
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
        ${getReceiptButtonHtml(order.id, order.status)}
      </div>
    </div>
  `;
}

async function openOrderDetails(orderId) {
  const loading = document.getElementById("orderDetailLoading");
  const errorBox = document.getElementById("orderDetailError");
  const content = document.getElementById("orderDetailContent");

  if (loading) loading.classList.remove("d-none");
  if (errorBox) {
    errorBox.classList.add("d-none");
    errorBox.textContent = "";
  }
  if (content) {
    content.classList.add("d-none");
    content.innerHTML = "";
  }

  detailModal?.show();

  try {
    const response = await fetch(`${ORDER_DETAIL_API_BASE}${orderId}/`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(
        await parseErrorMessage(response, `Failed to load order details (${response.status})`),
      );
    }

    const order = await response.json();

    if (content) {
      content.innerHTML = `
        ${renderOrderSummary(order)}
        ${renderFulfilmentSection(order.producer_breakdown || [])}
        ${renderItemsSection(order.items || [])}
        ${renderProducerSection(order.producer_breakdown || [])}
        ${renderOrderFooter(order)}
      `;
      content.classList.remove("d-none");
    }

    if (loading) loading.classList.add("d-none");
  } catch (error) {
    if (loading) loading.classList.add("d-none");
    if (errorBox) {
      errorBox.textContent = error.message || "Failed to load order details.";
      errorBox.classList.remove("d-none");
    }
  }
}

function resetReorderModal() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  if (title) title.textContent = "Confirm Reorder";
  if (content) content.innerHTML = "";
  if (footer) footer.innerHTML = REORDER_PREVIEW_FOOTER;
}

function setReorderModalLoading() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  if (title) title.textContent = "Confirm Reorder";
  if (content) content.innerHTML = `<div class="text-muted">Loading reorder preview...</div>`;
  if (footer) footer.innerHTML = REORDER_PREVIEW_FOOTER;
}

function setReorderSubmittingState() {
  const confirmBtn = document.getElementById("confirmReorderBtn");
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Reordering...";
  }
}

function renderSimpleMessageCard(title, body, className = "alert-info") {
  return `
    <div class="alert ${className}">
      <div class="fw-semibold">${escapeHtml(title)}</div>
      ${body ? `<div class="small mt-1">${escapeHtml(body)}</div>` : ""}
    </div>
  `;
}

function renderReorderPreview(preview) {
  const hasChanges =
    (preview.unavailable_items || []).length ||
    (preview.quantity_adjusted_items || []).length ||
    (preview.price_changed_items || []).length ||
    (preview.producer_changed_items || []).length;

  return `
    ${renderSimpleMessageCard(
      hasChanges ? "Please review these changes before confirming." : "No changes detected.",
      "Only available items will be added to the cart after confirmation.",
      hasChanges ? "alert-warning" : "alert-success",
    )}

    <div class="mb-4">
      <h6>Available Items To Be Added</h6>
      ${(preview.addable_items || []).length
        ? preview.addable_items.map((item) => `
            <div class="border rounded p-3 mb-2">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small text-muted">
                Producer: ${escapeHtml(item.producer_name)} |
                Quantity: ${escapeHtml(item.added_quantity)} |
                Current price: ${formatMoney(item.current_price)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No items can be added from this order.</div>`}
    </div>

    <div class="mb-4">
      <h6>Unavailable Items</h6>
      ${(preview.unavailable_items || []).length
        ? preview.unavailable_items.map((item) => `
            <div class="border border-danger rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small text-danger">
                Producer: ${escapeHtml(item.producer_name || "-")} |
                Requested: ${escapeHtml(item.requested_quantity)} |
                Reason: ${escapeHtml(item.reason)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No unavailable items.</div>`}
    </div>

    <div class="mb-4">
      <h6>Quantity Changes</h6>
      ${(preview.quantity_adjusted_items || []).length
        ? preview.quantity_adjusted_items.map((item) => `
            <div class="border border-warning rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small">
                Requested: ${escapeHtml(item.requested_quantity)} |
                Will add: ${escapeHtml(item.added_quantity)} |
                Reason: ${escapeHtml(item.reason)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No quantity changes.</div>`}
    </div>

    <div class="mb-4">
      <h6>Price Changes</h6>
      ${(preview.price_changed_items || []).length
        ? preview.price_changed_items.map((item) => `
            <div class="border border-primary rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small text-primary">
                Original price: ${formatMoney(item.original_price)} |
                Current price: ${formatMoney(item.current_price)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No price changes.</div>`}
    </div>

    <div class="mb-0">
      <h6>Producer Changes</h6>
      ${(preview.producer_changed_items || []).length
        ? preview.producer_changed_items.map((item) => `
            <div class="border border-secondary rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small">
                Previous producer: ${escapeHtml(item.original_producer_name)} |
                Current producer: ${escapeHtml(item.current_producer_name)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No producer changes.</div>`}
    </div>
  `;
}

function renderReorderResult(result) {
  return `
    ${renderSimpleMessageCard(
      result.message || "Reorder completed.",
      `Added: ${(result.added_items || []).length} | Unavailable: ${(result.unavailable_items || []).length} | Quantity adjusted: ${(result.quantity_adjusted_items || []).length} | Price changed: ${(result.price_changed_items || []).length}`,
      "alert-info",
    )}

    <div class="mb-4">
      <h6>Added to Cart</h6>
      ${(result.added_items || []).length
        ? result.added_items.map((item) => `
            <div class="border rounded p-3 mb-2">
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
            <div class="border border-danger rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small text-danger">
                Producer: ${escapeHtml(item.producer_name || "-")} |
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
            <div class="border border-warning rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small">
                Requested: ${escapeHtml(item.requested_quantity)} |
                Added: ${escapeHtml(item.added_quantity)} |
                Reason: ${escapeHtml(item.reason)}
              </div>
            </div>
          `).join("")
        : `<div class="text-muted">No quantity adjustments.</div>`}
    </div>

    <div class="mb-0">
      <h6>Price Changes</h6>
      ${(result.price_changed_items || []).length
        ? result.price_changed_items.map((item) => `
            <div class="border border-primary rounded p-3 mb-2 bg-light">
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

async function openReorderPreview(orderId) {
  pendingReorderOrderId = orderId;
  setReorderModalLoading();
  reorderModal?.show();

  try {
    const response = await fetch(`${ORDER_DETAIL_API_BASE}${orderId}${ORDER_REORDER_PREVIEW_API_SUFFIX}`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(
        await parseErrorMessage(response, `Failed to load reorder preview (${response.status})`),
      );
    }

    const preview = await response.json();
    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");

    if (content) {
      content.innerHTML = renderReorderPreview(preview);
    }

    const addableItems = Array.isArray(preview.addable_items) ? preview.addable_items : [];
    const addedItems = Array.isArray(preview.added_items) ? preview.added_items : [];
    const unavailableItems = Array.isArray(preview.unavailable_items) ? preview.unavailable_items : [];
    const quantityAdjustedItems = Array.isArray(preview.quantity_adjusted_items) ? preview.quantity_adjusted_items : [];
    const priceChangedItems = Array.isArray(preview.price_changed_items) ? preview.price_changed_items : [];
    const producerChangedItems = Array.isArray(preview.producer_changed_items) ? preview.producer_changed_items : [];

    const hasExplicitAddableItems = addableItems.length > 0;

    const hasAnyReorderableSignal =
      hasExplicitAddableItems ||
      addedItems.length > 0 ||
      quantityAdjustedItems.length > 0 ||
      priceChangedItems.length > 0 ||
      producerChangedItems.length > 0;

    const definitelyNothingToAdd =
      !hasAnyReorderableSignal &&
      unavailableItems.length > 0;

    if (footer) {
      footer.innerHTML = definitelyNothingToAdd
        ? `
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
            Close
          </button>
        `
        : REORDER_PREVIEW_FOOTER;
    }
  } catch (error) {
    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");

    if (content) {
      content.innerHTML = `
        <div class="alert alert-danger mb-0">
          ${escapeHtml(error.message || "Failed to load reorder preview.")}
        </div>
      `;
    }

    if (footer) {
      footer.innerHTML = `
        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
          Close
        </button>
      `;
    }
  }
}

async function confirmReorder(orderId) {
  try {
    setReorderSubmittingState();

    const response = await fetch(`${ORDER_DETAIL_API_BASE}${orderId}${ORDER_REORDER_API_SUFFIX}`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(
        await parseErrorMessage(response, `Reorder failed (${response.status})`),
      );
    }

    const result = await response.json();

    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");
    const title = document.getElementById("reorderModalTitle");

    if (title) title.textContent = "Reorder Result";
    if (content) content.innerHTML = renderReorderResult(result);
    if (footer) footer.innerHTML = REORDER_RESULT_FOOTER;

    document.dispatchEvent(new CustomEvent("cart:updated", { detail: { action: "reorder" } }));

    try {
      await window.CartAPI?.getCartBadgeCount?.();
    } catch (_) {
      // ignore cart badge refresh failure
    }

    pendingReorderOrderId = null;
  } catch (error) {
    const content = document.getElementById("reorderModalContent");
    const confirmBtn = document.getElementById("confirmReorderBtn");

    if (content) {
      content.insertAdjacentHTML(
        "afterbegin",
        `
          <div class="alert alert-danger">
            ${escapeHtml(error.message || "Reorder failed.")}
          </div>
        `,
      );
    }

    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Confirm Reorder";
    }
  }
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