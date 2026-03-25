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

const REORDER_RESULT_FOOTER = `
  <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
    Close
  </button>
  <a href="/cart/" class="btn btn-primary">Go to Cart</a>
`;

let appliedFilters = { ...DEFAULT_FILTERS };
let currentPage = 1;
let totalCount = 0;
let pageSize = 10;

let detailModal = null;
let reorderModal = null;
let pendingReorderOrderId = null;
let reorderPlannerState = null;

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
      return;
    }

    const qtyMinusBtn = event.target.closest("[data-action='reorder-qty-minus']");
    if (qtyMinusBtn) {
      const groupId = qtyMinusBtn.dataset.groupId;
      changeGroupQuantity(groupId, -1);
      return;
    }

    const qtyPlusBtn = event.target.closest("[data-action='reorder-qty-plus']");
    if (qtyPlusBtn) {
      const groupId = qtyPlusBtn.dataset.groupId;
      changeGroupQuantity(groupId, 1);
    }
  });

  document.addEventListener("change", (event) => {
    const optionInput = event.target.closest(".js-reorder-option-input");
    if (optionInput) {
      const groupId = optionInput.dataset.groupId;
      const optionKey = optionInput.dataset.optionKey;
      updateGroupSelectedOption(groupId, optionKey);
      return;
    }

    const qtyInput = event.target.closest(".js-reorder-qty-input");
    if (qtyInput) {
      const groupId = qtyInput.dataset.groupId;
      updateGroupQuantity(groupId, qtyInput.value);
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
      class="btn btn-primary ${escapeHtml(extraClass)}"
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
        class="btn btn-primary"
        disabled
        title="Receipt is only available for completed orders"
      >
        See Receipt
      </button>
    `;
  }

  return `
    <a
      class="btn btn-primary"
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
          class="btn btn-sm btn-primary me-2"
          data-action="view-details"
          data-order-id="${escapeHtml(order.id)}"
        >
          View Details
        </button>
        ${getReorderButtonHtml(order.id, order.order_status, "btn-sm btn-primary")}
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

/* =========================
   REORDER PLANNER HELPERS
   ========================= */

function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function makeDomSafeId(value) {
  return String(value || "")
    .replaceAll(":", "-")
    .replaceAll(" ", "-")
    .replaceAll("/", "-")
    .replaceAll(".", "-");
}

function clampQuantity(quantity, maxAvailable) {
  const parsed = Math.max(1, parseInt(quantity, 10) || 1);

  if (maxAvailable === null || maxAvailable === undefined || maxAvailable === "") {
    return parsed;
  }

  const max = Math.max(1, parseInt(maxAvailable, 10) || 1);
  return Math.min(parsed, max);
}

function buildLookupByOrderItemId(items) {
  const lookup = new Map();

  ensureArray(items).forEach((item) => {
    if (item && item.order_item_id !== null && item.order_item_id !== undefined) {
      lookup.set(String(item.order_item_id), item);
    }
  });

  return lookup;
}

function createOptionFromAddableItem(item) {
  return {
    key: `keep:${item.product_id}:${item.inventory_id ?? "none"}`,
    action: "keep",
    product_id: item.product_id,
    product_name: item.product_name,
    producer_id: item.producer_id,
    producer_name: item.producer_name,
    inventory_id: item.inventory_id ?? null,
    available_quantity: item.available_quantity ?? item.added_quantity ?? item.requested_quantity ?? null,
    current_price: item.current_price,
    pricing: item.pricing || null,
    match_basis: item.match_basis || "same_product",
    source_label: "Original product",
  };
}

function createOptionFromSuggestedItem(item) {
  return {
    key: `replace:${item.product_id}:${item.inventory_id ?? "none"}`,
    action: "replace",
    product_id: item.product_id,
    product_name: item.product_name,
    producer_id: item.producer_id,
    producer_name: item.producer_name,
    inventory_id: item.inventory_id ?? null,
    available_quantity: item.available_quantity ?? null,
    current_price: item.current_price,
    pricing: item.pricing || null,
    match_basis: item.match_basis || "",
    source_label: "Alternative product",
  };
}

function createSkipOption(groupId) {
  return {
    key: `skip:${groupId}`,
    action: "skip",
    product_id: null,
    product_name: "Skip this item",
    producer_id: null,
    producer_name: "",
    inventory_id: null,
    available_quantity: null,
    current_price: 0,
    pricing: null,
    match_basis: "",
    source_label: "Skip",
  };
}

function buildReorderPlannerState(orderId, preview) {
  const quantityAdjustedLookup = buildLookupByOrderItemId(preview.quantity_adjusted_items);
  const priceChangedLookup = buildLookupByOrderItemId(preview.price_changed_items);
  const producerChangedLookup = buildLookupByOrderItemId(preview.producer_changed_items);

  const groups = [];

  ensureArray(preview.addable_items).forEach((item, index) => {
    const groupId = String(item.order_item_id ?? `available-${index}`);
    const originalRequestedQuantity = toNumber(
      item.requested_quantity ?? item.added_quantity,
      1,
    );

    const originalOption = createOptionFromAddableItem(item);
    const suggestedOptions = ensureArray(item.suggested_items).map(createOptionFromSuggestedItem);

    groups.push({
      groupId,
      orderItemId: item.order_item_id ?? null,
      kind: "available",
      original: {
        product_name: item.product_name,
        producer_name: item.producer_name,
        requested_quantity: originalRequestedQuantity,
        reason: null,
      },
      selectedOptionKey: originalOption.key,
      quantity: clampQuantity(
        originalRequestedQuantity,
        originalOption.available_quantity,
      ),
      options: [originalOption, ...suggestedOptions],
      signals: {
        quantityAdjusted: quantityAdjustedLookup.get(groupId) || null,
        priceChanged: priceChangedLookup.get(groupId) || null,
        producerChanged: producerChangedLookup.get(groupId) || null,
      },
    });
  });

  ensureArray(preview.unavailable_items).forEach((item, index) => {
    const groupId = String(item.order_item_id ?? `unavailable-${index}`);
    const originalRequestedQuantity = toNumber(item.requested_quantity, 1);
    const suggestedOptions = ensureArray(item.suggested_items).map(createOptionFromSuggestedItem);
    const hasSuggestions = suggestedOptions.length > 0;
    const selectedOption = hasSuggestions ? suggestedOptions[0] : createSkipOption(groupId);

    groups.push({
      groupId,
      orderItemId: item.order_item_id ?? null,
      kind: hasSuggestions ? "needs-choice" : "unavailable",
      original: {
        product_name: item.product_name,
        producer_name: item.producer_name || "",
        requested_quantity: originalRequestedQuantity,
        reason: item.reason || "Unavailable",
      },
      selectedOptionKey: selectedOption.key,
      quantity: hasSuggestions
        ? clampQuantity(originalRequestedQuantity, selectedOption.available_quantity)
        : 0,
      options: hasSuggestions
        ? [...suggestedOptions, createSkipOption(groupId)]
        : [createSkipOption(groupId)],
      signals: {
        quantityAdjusted: quantityAdjustedLookup.get(groupId) || null,
        priceChanged: priceChangedLookup.get(groupId) || null,
        producerChanged: producerChangedLookup.get(groupId) || null,
      },
    });
  });

  return {
    orderId,
    preview,
    groups,
  };
}

function getGroupById(groupId) {
  if (!reorderPlannerState) return null;
  return reorderPlannerState.groups.find((group) => String(group.groupId) === String(groupId)) || null;
}

function getSelectedOption(group) {
  if (!group) return null;
  return group.options.find((option) => option.key === group.selectedOptionKey) || null;
}

function getPlannerStats() {
  if (!reorderPlannerState) {
    return {
      selectedCount: 0,
      skippedCount: 0,
      estimatedSubtotal: 0,
      actionableCount: 0,
    };
  }

  return reorderPlannerState.groups.reduce((stats, group) => {
    const selectedOption = getSelectedOption(group);

    if (!selectedOption || selectedOption.action === "skip") {
      stats.skippedCount += 1;
      return stats;
    }

    const quantity = clampQuantity(group.quantity, selectedOption.available_quantity);
    const unitPrice = toNumber(
      selectedOption.pricing?.effective_unit_price ?? selectedOption.current_price,
      0,
    );

    stats.selectedCount += 1;
    stats.actionableCount += 1;
    stats.estimatedSubtotal += quantity * unitPrice;
    return stats;
  }, {
    selectedCount: 0,
    skippedCount: 0,
    estimatedSubtotal: 0,
    actionableCount: 0,
  });
}

function serializeSelectionsFromState() {
  if (!reorderPlannerState) return [];

  return reorderPlannerState.groups
    .map((group) => {
      const selectedOption = getSelectedOption(group);

      if (!selectedOption || group.orderItemId === null || group.orderItemId === undefined) {
        return null;
      }

      if (selectedOption.action === "skip") {
        return {
          order_item_id: group.orderItemId,
          action: "skip",
        };
      }

      return {
        order_item_id: group.orderItemId,
        action: selectedOption.action,
        selected_product_id: selectedOption.product_id,
        inventory_id: selectedOption.inventory_id,
        quantity: clampQuantity(group.quantity, selectedOption.available_quantity),
      };
    })
    .filter(Boolean);
}

function updateGroupSelectedOption(groupId, optionKey) {
  const group = getGroupById(groupId);
  if (!group) return;

  group.selectedOptionKey = optionKey;

  const selectedOption = getSelectedOption(group);
  if (!selectedOption) return;

  if (selectedOption.action === "skip") {
    group.quantity = 0;
  } else {
    const fallbackQuantity = group.quantity || group.original.requested_quantity || 1;
    group.quantity = clampQuantity(fallbackQuantity, selectedOption.available_quantity);
  }

  updateReorderPlannerUI();
}

function updateGroupQuantity(groupId, rawValue) {
  const group = getGroupById(groupId);
  if (!group) return;

  const selectedOption = getSelectedOption(group);
  if (!selectedOption || selectedOption.action === "skip") return;

  group.quantity = clampQuantity(rawValue, selectedOption.available_quantity);
  updateReorderPlannerUI();
}

function changeGroupQuantity(groupId, delta) {
  const group = getGroupById(groupId);
  if (!group) return;

  const selectedOption = getSelectedOption(group);
  if (!selectedOption || selectedOption.action === "skip") return;

  const current = clampQuantity(group.quantity, selectedOption.available_quantity);
  group.quantity = clampQuantity(current + delta, selectedOption.available_quantity);
  updateReorderPlannerUI();
}

function renderSimpleMessageCard(title, body, className = "alert-info") {
  return `
    <div class="alert ${className}">
      <div class="fw-semibold">${escapeHtml(title)}</div>
      ${body ? `<div class="small mt-1">${escapeHtml(body)}</div>` : ""}
    </div>
  `;
}

function renderPlannerSummaryCard() {
  const stats = getPlannerStats();
  const previewMessage = reorderPlannerState?.preview?.message || "Review your selections before adding items to cart.";

  return `
    <div class="border rounded p-3 mb-4 bg-light">
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
        <div>
          <div class="fw-semibold mb-1">Review Reorder</div>
          <div class="small text-muted">
            ${escapeHtml(previewMessage)}
          </div>
        </div>
        <div class="text-md-end">
          <div class="small text-muted">Estimated subtotal</div>
          <div class="fs-5 fw-bold">${formatMoney(stats.estimatedSubtotal)}</div>
        </div>
      </div>

      <div class="d-flex flex-wrap gap-2 mt-3">
        <span class="badge text-bg-light border">Selected items: ${escapeHtml(stats.selectedCount)}</span>
        <span class="badge text-bg-light border">Skipped items: ${escapeHtml(stats.skippedCount)}</span>
      </div>
    </div>
  `;
}

function renderPlannerSection(title, subtitle, groups) {
  if (!groups.length) {
    return "";
  }

  return `
    <div class="mb-4">
      <div class="mb-3">
        <h6 class="mb-1">${escapeHtml(title)}</h6>
        ${subtitle ? `<div class="small text-muted">${escapeHtml(subtitle)}</div>` : ""}
      </div>
      ${groups.map((group) => renderPlannerGroup(group)).join("")}
    </div>
  `;
}

function renderMatchBasisLabel(matchBasis) {
  const value = String(matchBasis || "").replaceAll("_", " ").trim();
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderOptionBadges(group, option) {
  const badges = [];

  if (group.kind === "available" && option.action === "keep") {
    badges.push(`<span class="badge rounded-pill text-bg-light border me-1 mb-1">Original product</span>`);
  }

  if (option.action === "replace") {
    badges.push(`<span class="badge rounded-pill text-bg-light border me-1 mb-1">Alternative producer</span>`);
  }

  if (option.match_basis && option.match_basis !== "same_product") {
    badges.push(`
      <span class="badge rounded-pill text-bg-light border me-1 mb-1">
        ${escapeHtml(renderMatchBasisLabel(option.match_basis))} match
      </span>
    `);
  }

  if (option.pricing?.surplus?.is_active) {
    badges.push(`<span class="badge rounded-pill text-bg-light border me-1 mb-1">Surplus</span>`);
  }

  if (option.pricing?.wholesale?.has_wholesale_tiers) {
    const label = option.pricing?.wholesale?.active_for_quantity
      ? "Wholesale active"
      : "Wholesale available";
    badges.push(`<span class="badge rounded-pill text-bg-light border me-1 mb-1">${escapeHtml(label)}</span>`);
  }

  return badges.join("");
}

function renderQuantityAdjustmentNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-warning-emphasis mt-2">
      Requested ${escapeHtml(signal.requested_quantity)} · available now ${escapeHtml(signal.added_quantity)}.
      ${escapeHtml(signal.reason || "")}
    </div>
  `;
}

function renderPriceChangeNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-primary mt-2">
      Price changed from ${formatMoney(signal.original_price)} to ${formatMoney(signal.current_price)}.
    </div>
  `;
}

function renderProducerChangeNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-secondary mt-2">
      Producer change: ${escapeHtml(signal.original_producer_name)} → ${escapeHtml(signal.current_producer_name)}.
    </div>
  `;
}

function renderPricingHelper(option, quantity) {
  const pricing = option.pricing || {};
  const wholesale = pricing.wholesale || null;

  if (wholesale?.active_for_quantity) {
    return `<div class="small text-success mt-1">Wholesale active at this quantity.</div>`;
  }

  if (wholesale?.has_wholesale_tiers && wholesale?.next_tier?.min_quantity) {
    const nextTierQuantity = toNumber(wholesale.next_tier.min_quantity, 0);
    if (nextTierQuantity > quantity) {
      const difference = nextTierQuantity - quantity;
      return `
        <div class="small text-muted mt-1">
          Add ${escapeHtml(difference)} more to unlock ${formatMoney(wholesale.next_tier.unit_price)} per unit.
        </div>
      `;
    }
  }

  if (pricing?.surplus?.is_active) {
    return `<div class="small text-success mt-1">Surplus discount is active for this option.</div>`;
  }

  return "";
}

function renderQuantityControls(group, option) {
  const quantity = clampQuantity(group.quantity, option.available_quantity);
  const minusDisabled = quantity <= 1 ? "disabled" : "";
  const plusDisabled = option.available_quantity !== null && option.available_quantity !== undefined
    ? quantity >= toNumber(option.available_quantity, quantity)
      ? "disabled"
      : ""
    : "";

  const stockNote = option.available_quantity !== null && option.available_quantity !== undefined
    ? `<div class="small text-muted mt-1">Available now: ${escapeHtml(option.available_quantity)}</div>`
    : "";

  return `
    <div class="mt-3 pt-3 border-top">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label small text-muted mb-1">Quantity</label>
          <div class="input-group">
            <button
              type="button"
              class="btn btn-outline-secondary"
              data-action="reorder-qty-minus"
              data-group-id="${escapeHtml(group.groupId)}"
              ${minusDisabled}
            >
              −
            </button>
            <input
              type="number"
              min="1"
              ${option.available_quantity !== null && option.available_quantity !== undefined ? `max="${escapeHtml(option.available_quantity)}"` : ""}
              class="form-control text-center js-reorder-qty-input"
              data-group-id="${escapeHtml(group.groupId)}"
              value="${escapeHtml(quantity)}"
            >
            <button
              type="button"
              class="btn btn-outline-secondary"
              data-action="reorder-qty-plus"
              data-group-id="${escapeHtml(group.groupId)}"
              ${plusDisabled}
            >
              +
            </button>
          </div>
          ${stockNote}
        </div>

        <div class="col-md-8">
          <div class="small text-muted">Pricing</div>
          <div class="fw-semibold">
            ${formatMoney(option.pricing?.effective_unit_price ?? option.current_price)} each
          </div>
          <div class="small text-muted">
            Base: ${formatMoney(option.pricing?.base_unit_price ?? option.current_price)} each
          </div>
          ${renderPricingHelper(option, quantity)}
        </div>
      </div>
    </div>
  `;
}

function renderOptionCard(group, option) {
  const selected = option.key === group.selectedOptionKey;
  const inputId = `reorder-option-${makeDomSafeId(group.groupId)}-${makeDomSafeId(option.key)}`;
  const cardClass = selected
    ? "border-primary shadow-sm"
    : "border";

  if (group.kind === "unavailable" && option.action === "skip") {
    return `
      <div class="border rounded p-3 bg-light">
        <div class="fw-semibold">No alternative currently available</div>
        <div class="small text-muted mt-1">
          This item cannot be reordered right now.
        </div>
      </div>
    `;
  }

  return `
    <div class="rounded p-3 mb-2 ${cardClass}">
      <div class="form-check">
        <input
          class="form-check-input js-reorder-option-input"
          type="radio"
          name="reorder-choice-${escapeHtml(group.groupId)}"
          id="${escapeHtml(inputId)}"
          data-group-id="${escapeHtml(group.groupId)}"
          data-option-key="${escapeHtml(option.key)}"
          ${selected ? "checked" : ""}
        >
        <label class="form-check-label d-block" for="${escapeHtml(inputId)}">
          <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
            <div>
              <div class="fw-semibold">${escapeHtml(option.product_name)}</div>
              <div class="small text-muted">
                ${option.producer_name ? `${escapeHtml(option.producer_name)} · ` : ""}${escapeHtml(option.source_label)}
              </div>
            </div>
            <div class="text-md-end">
              <div class="fw-semibold">
                ${option.action === "skip" ? "Skip" : formatMoney(option.pricing?.effective_unit_price ?? option.current_price)}
              </div>
              ${option.action !== "skip" ? `<div class="small text-muted">per unit</div>` : ""}
            </div>
          </div>

          <div class="mt-2">
            ${renderOptionBadges(group, option)}
          </div>

          ${option.action !== "skip" ? `
            <div class="small text-muted mt-2">
              ${option.available_quantity !== null && option.available_quantity !== undefined
                ? `Available: ${escapeHtml(option.available_quantity)}`
                : "Availability not specified"}
            </div>
          ` : `
            <div class="small text-muted mt-2">
              This item will not be added to the cart.
            </div>
          `}
        </label>
      </div>

      ${selected && option.action !== "skip" ? renderQuantityControls(group, option) : ""}
    </div>
  `;
}

function renderPlannerGroup(group) {
  const selectedOption = getSelectedOption(group);
  const alternativeCount = Math.max(0, group.options.filter((option) => option.action === "replace").length);

  let groupTitle = "Ready to add";
  let groupSubtitle = "Original product is available.";

  if (group.kind === "needs-choice") {
    groupTitle = "Choose a replacement";
    groupSubtitle = "Original product is unavailable. Pick an alternative or skip this item.";
  } else if (group.kind === "unavailable") {
    groupTitle = "Not currently available";
    groupSubtitle = "No alternative product was found.";
  } else if (alternativeCount > 0) {
    groupSubtitle = "Original product is available. Alternative producer options are also shown.";
  }

  return `
    <div class="card mb-3">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-3">
          <div>
            <div class="small text-muted">${escapeHtml(groupTitle)}</div>
            <h6 class="mb-1">${escapeHtml(group.original.product_name)}</h6>
            <div class="small text-muted">
              ${group.original.producer_name ? `${escapeHtml(group.original.producer_name)} · ` : ""}Requested quantity: ${escapeHtml(group.original.requested_quantity)}
            </div>
            <div class="small text-muted mt-1">${escapeHtml(groupSubtitle)}</div>
            ${group.original.reason ? `<div class="small text-danger mt-1">Reason: ${escapeHtml(group.original.reason)}</div>` : ""}
          </div>

          <div class="text-md-end">
            ${selectedOption && selectedOption.action !== "skip"
              ? `
                <div class="small text-muted">Selected</div>
                <div class="fw-semibold">${escapeHtml(selectedOption.product_name)}</div>
                <div class="small text-muted">${escapeHtml(selectedOption.producer_name || "")}</div>
              `
              : `
                <div class="small text-muted">Selected</div>
                <div class="fw-semibold">Skip this item</div>
              `}
          </div>
        </div>

        ${renderQuantityAdjustmentNotice(group.signals.quantityAdjusted)}
        ${renderPriceChangeNotice(group.signals.priceChanged)}
        ${renderProducerChangeNotice(group.signals.producerChanged)}

        <div class="mt-3">
          ${group.options.map((option) => renderOptionCard(group, option)).join("")}
        </div>
      </div>
    </div>
  `;
}

function renderReorderPlanner() {
  if (!reorderPlannerState || !reorderPlannerState.groups.length) {
    return `
      ${renderSimpleMessageCard(
        "No reorderable items found.",
        "This order does not currently contain any items that can be reordered.",
        "alert-warning",
      )}
    `;
  }

  const availableGroups = reorderPlannerState.groups.filter((group) => group.kind === "available");
  const needsChoiceGroups = reorderPlannerState.groups.filter((group) => group.kind === "needs-choice");
  const unavailableGroups = reorderPlannerState.groups.filter((group) => group.kind === "unavailable");

  return `
    ${renderPlannerSummaryCard()}

    ${renderPlannerSection(
      "Ready to add",
      "These products are still available and are selected by default.",
      availableGroups,
    )}

    ${renderPlannerSection(
      "Choose replacements",
      "These original products are unavailable, so choose an alternative producer/product or skip them.",
      needsChoiceGroups,
    )}

    ${renderPlannerSection(
      "Not available",
      "These products currently have no replacement options.",
      unavailableGroups,
    )}
  `;
}

function getReorderPlannerFooterHtml() {
  const stats = getPlannerStats();

  if (!reorderPlannerState || !reorderPlannerState.groups.length || stats.actionableCount === 0) {
    return `
      <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
        Close
      </button>
    `;
  }

  return `
    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
      Cancel
    </button>
    <button type="button" class="btn btn-primary" id="confirmReorderBtn">
      Add Selected Items to Cart
    </button>
  `;
}

function updateReorderPlannerUI() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  if (title) title.textContent = "Review Reorder";
  if (content) content.innerHTML = renderReorderPlanner();
  if (footer) footer.innerHTML = getReorderPlannerFooterHtml();
}

/* =========================
   REORDER MODAL STATES
   ========================= */

function resetReorderModal() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  reorderPlannerState = null;

  if (title) title.textContent = "Confirm Reorder";
  if (content) content.innerHTML = "";
  if (footer) {
    footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
        Cancel
      </button>
      <button type="button" class="btn btn-primary" id="confirmReorderBtn" disabled>
        Confirm Reorder
      </button>
    `;
  }
}

function setReorderModalLoading() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  reorderPlannerState = null;

  if (title) title.textContent = "Review Reorder";
  if (content) content.innerHTML = `<div class="text-muted">Loading reorder preview...</div>`;
  if (footer) {
    footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
        Cancel
      </button>
      <button type="button" class="btn btn-primary" id="confirmReorderBtn" disabled>
        Add Selected Items to Cart
      </button>
    `;
  }
}

function setReorderSubmittingState() {
  const confirmBtn = document.getElementById("confirmReorderBtn");
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Adding to Cart...";
  }
}

/* =========================
   REORDER RESULT RENDERING
   ========================= */

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

/* =========================
   REORDER API ACTIONS
   ========================= */

async function openReorderPreview(orderId) {
  pendingReorderOrderId = orderId;
  setReorderModalLoading();
  reorderModal?.show();

  try {
    const response = await fetch(
      `${ORDER_DETAIL_API_BASE}${orderId}${ORDER_REORDER_PREVIEW_API_SUFFIX}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({}),
        credentials: "same-origin",
      },
    );

    if (!response.ok) {
      throw new Error(
        await parseErrorMessage(response, `Failed to load reorder preview (${response.status})`),
      );
    }

    const preview = await response.json();
    reorderPlannerState = buildReorderPlannerState(orderId, preview);
    updateReorderPlannerUI();
  } catch (error) {
    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");
    const title = document.getElementById("reorderModalTitle");

    reorderPlannerState = null;

    if (title) title.textContent = "Review Reorder";
    if (content) {
      content.innerHTML = `
        <div class="alert alert-danger mb-0">
          ${escapeHtml(error.message || "Failed to load reorder preview.")}
        </div>
      `;
    }

    if (footer) {
      footer.innerHTML = `
        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
          Close
        </button>
      `;
    }
  }
}

async function confirmReorder(orderId) {
  try {
    setReorderSubmittingState();

    const payload = {
      selections: serializeSelectionsFromState(),
    };

    const response = await fetch(
      `${ORDER_DETAIL_API_BASE}${orderId}${ORDER_REORDER_API_SUFFIX}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      },
    );

    if (!response.ok) {
      throw new Error(
        await parseErrorMessage(response, `Reorder failed (${response.status})`),
      );
    }

    const result = await response.json();

    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");
    const title = document.getElementById("reorderModalTitle");

    reorderPlannerState = null;

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
      confirmBtn.textContent = "Add Selected Items to Cart";
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