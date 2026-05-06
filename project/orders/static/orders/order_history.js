const ORDER_HISTORY_API_URL = "/api/orders/history/";
const ORDER_DETAIL_API_BASE = "/api/orders/";
const ORDER_REORDER_PREVIEW_API_SUFFIX = "/reorder-preview/";
const ORDER_REORDER_API_SUFFIX = "/reorder/";
const RECEIPT_URL_BASE = "/orders/receipt/";
const REVIEW_ADD_PAGE_URL = "/reviews/add/";
const M = window.OrderHistoryMessages;

const DEFAULT_FILTERS = {
  order_reference: "",
  status: "",
  start_date: "",
  end_date: "",
  delivery_or_collection: "",
};

const REORDER_RESULT_FOOTER = `
  <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
    ${M.closeButton}
  </button>
  <a href="/cart/" class="btn btn-primary">${M.goToCartButton}</a>
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
    const writeReviewBtn = event.target.closest("[data-action='write-review']");
    if (writeReviewBtn) {
      handleWriteReviewClick(writeReviewBtn);
      return;
    }

    const reorderBtn = event.target.closest(
      "[data-action='open-reorder-preview']",
    );
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

    const qtyMinusBtn = event.target.closest(
      "[data-action='reorder-qty-minus']",
    );
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

function showReorderResultToasts(result) {
  const quantityAdjustedItems = ensureArray(result?.quantity_adjusted_items);
  const unavailableItems = ensureArray(result?.unavailable_items);

  quantityAdjustedItems.forEach((item) => {
    showOrderToast(M.getReorderItemReason(item), {
      title: M.cartTitle,
      variant: "danger",
      delay: 3500,
    });
  });

  unavailableItems
    .filter((item) => item?.reason_code === "cart_stock_limit_exceeded")
    .forEach((item) => {
      showOrderToast(M.getReorderItemReason(item), {
        title: M.cartTitle,
        variant: "danger",
        delay: 3500,
      });
    });
}

function readFiltersFromForm() {
  const orderReference = normaliseOrderReferenceSearch(
    document.getElementById("order_reference")?.value,
  );

  return {
    order_reference: orderReference,
    status: document.getElementById("status")?.value || "",
    start_date: document.getElementById("start_date")?.value || "",
    end_date: document.getElementById("end_date")?.value || "",
    delivery_or_collection:
      document.getElementById("delivery_or_collection")?.value || "",
  };
}

function writeFiltersToForm(filters) {
  const fields = [
    "order_reference",
    "status",
    "start_date",
    "end_date",
    "delivery_or_collection",
  ];

  fields.forEach((field) => {
    const el = document.getElementById(field);

    if (el) {
      el.value = filters[field] || "";
    }
  });
}

function buildQueryString() {
  const params = new URLSearchParams();

  const hasOrderReferenceSearch = Boolean(appliedFilters.order_reference);

  Object.entries(appliedFilters).forEach(([key, value]) => {
    if (value === "") {
      return;
    }

    /*
      Important:
      When searching by order reference, do not send the status filter.
      This allows completed, cancelled, pending, and in-progress orders to be found.
    */
    if (hasOrderReferenceSearch && key === "status") {
      return;
    }

    params.append(key, value);
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
    showDateValidationError(M.startDateMin(MIN_ORDER_FILTER_DATE), [
      startDateEl,
    ]);
    return false;
  }

  if (endDate && endDate < MIN_ORDER_FILTER_DATE) {
    showDateValidationError(M.endDateMin(MIN_ORDER_FILTER_DATE), [endDateEl]);
    return false;
  }

  if (startDate && startDate > today) {
    showDateValidationError(M.startDateFuture, [startDateEl]);
    return false;
  }

  if (endDate && endDate > today) {
    showDateValidationError(M.endDateFuture, [endDateEl]);
    return false;
  }

  if (startDate && endDate && startDate > endDate) {
    showDateValidationError(M.startDateAfterEnd, [startDateEl, endDateEl]);
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
function normaliseOrderReferenceSearch(value) {
  return String(value || "")
    .trim()
    .replace(/^#+/, "")
    .toLowerCase()
    .replace(/\s+/g, "");
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

function isReorderAllowed(order) {
  const statusKey = String(
    order?.order_status_key || order?.status_key || "",
  ).toLowerCase();

  return statusKey === "completed";
}

function isReceiptAllowed(status) {
  const value = normaliseStatus(status);
  return !value.includes("cancel");
}

function isCustomerCancellationAllowed(order) {
  return Boolean(order?.can_customer_cancel);
}

function getCustomerCancelButtonHtml(order) {
  const orderId = order?.id || order?.order_id;

  if (!orderId) {
    return "";
  }

  const status = order?.status || order?.order_status || "";
  const allowed = isCustomerCancellationAllowed(order);
  const disabledAttr = allowed ? "" : "disabled";
  const title = allowed
    ? "Cancel this order before producers start preparing it."
    : "Cancellation is only available while the order is pending.";

  return `
    <button
      type="button"
      class="btn btn-danger"
      data-action="cancel-customer-order"
      data-order-id="${escapeHtml(orderId)}"
      data-order-number="${escapeHtml(order.order_number || orderId)}"
      ${disabledAttr}
      title="${escapeHtml(title)}"
    >
      Cancel order
    </button>
  `;
}

function isCustomerItemCancellationAllowed(item) {
  return Boolean(item?.can_customer_cancel_item);
}

function getCustomerCancelItemButtonHtml(order, item) {
  const orderId = order?.id || order?.order_id;
  const itemId = item?.id;
  const activeQuantity = Number(item?.active_quantity ?? item?.quantity ?? 0);
  const allowed = isCustomerItemCancellationAllowed(item) && activeQuantity > 0;

  if (!orderId || !itemId) {
    return "";
  }

  const disabledAttr = allowed ? "" : "disabled";
  const title = allowed
    ? "Cancel this item before the producer starts preparing it."
    : "Item cancellation is only available before the producer starts preparing it.";

  return `
    <button
      type="button"
      class="btn btn-sm btn-danger"
      data-action="cancel-customer-order-item"
      data-order-id="${escapeHtml(orderId)}"
      data-item-id="${escapeHtml(itemId)}"
      data-product-name="${escapeHtml(item.product_name || "this item")}"
      data-active-quantity="${escapeHtml(activeQuantity)}"
      ${disabledAttr}
      title="${escapeHtml(title)}"
    >
      Cancel item
    </button>
  `;
}

function getReorderButtonHtml(order, extraClass = "") {
  const orderId = order?.id || order?.order_id;
  const allowed = isReorderAllowed(order);
  const disabledAttr = allowed ? "" : "disabled";
  const title = allowed ? M.reorderAllowedTooltip : M.reorderBlockedTooltip;

  if (!orderId) {
    return "";
  }

  return `
    <button
      type="button"
      class="btn btn-primary ${escapeHtml(extraClass)}"
      data-action="open-reorder-preview"
      data-order-id="${escapeHtml(orderId)}"
      ${disabledAttr}
      title="${escapeHtml(title)}"
    >
      ${M.reorderButton}
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
        title="${escapeHtml(M.receiptBlockedTooltip)}"
      >
        ${M.receiptButton}
      </button>
    `;
  }

  return `
    <a
      class="btn btn-primary"
      href="${RECEIPT_URL_BASE}${orderId}/"
    >
      ${M.receiptButton}
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
    paginationInfo.textContent =
      totalCount === 0 ? M.zeroOrders : M.pageOnly(currentPage);
  }

  if (prevBtn) prevBtn.disabled = true;
  if (nextBtn) nextBtn.disabled = true;
}

function setErrorState(message) {
  document.getElementById("orderListLoading")?.classList.add("d-none");
  document.getElementById("orderTableWrapper")?.classList.add("d-none");

  const errorBox = document.getElementById("orderListError");
  if (errorBox) {
    errorBox.textContent = message || M.loadFailed;
    errorBox.classList.remove("d-none");
  }
}

function setPaginationState(totalPages) {
  const paginationInfo = document.getElementById("paginationInfo");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");

  if (paginationInfo) {
    paginationInfo.textContent = M.pageSummary(
      currentPage,
      totalPages,
      totalCount,
    );
  }

  if (prevBtn) prevBtn.disabled = currentPage <= 1;
  if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
}

async function buildApiErrorFromResponse(response, fallbackMessage) {
  let payload = null;

  try {
    payload = await response.clone().json();
  } catch {
    payload = null;
  }

  const message = payload
    ? window.AppApiErrors.fromPayload(payload, fallbackMessage)
    : await window.AppApiErrors.fromResponse(response, fallbackMessage);

  const error = new Error(message || fallbackMessage);
  error.status = response.status;
  error.payload = payload;
  return error;
}

function showOrderToast(
  message,
  { title = M.cartTitle || "Cart", variant = "warning", delay = 3000 } = {},
) {
  if (!message) return;

  if (typeof window.CartAPI?.showToast === "function") {
    window.CartAPI.showToast(message, {
      title,
      variant,
      delay,
    });
    return;
  }

  const errorBox = document.getElementById("orderListError");
  if (errorBox) {
    errorBox.textContent = message;
    errorBox.classList.remove("d-none");
  }
}

function toPositiveInteger(value) {
  const number = Number(value);

  if (!Number.isFinite(number) || number < 1) {
    return null;
  }

  return Math.floor(number);
}

function getQuantityLimitToastMessage(
  group,
  selectedOption,
  requestedQuantity,
) {
  const availableQuantity = toPositiveInteger(
    selectedOption?.available_quantity,
  );

  if (!availableQuantity) {
    return null;
  }

  const productName =
    selectedOption?.product_name ||
    group?.original?.product_name ||
    M.productFallback ||
    "this item";

  if (requestedQuantity <= availableQuantity) {
    return null;
  }

  return M.reorderQuantityLimitToast(productName, availableQuantity);
}

async function loadOrders() {
  setLoadingState();

  try {
    const response = await fetch(
      `${ORDER_HISTORY_API_URL}?${buildQueryString()}`,
      {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      },
    );

    if (!response.ok) {
      throw await buildApiErrorFromResponse(response, M.loadFailed);
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
    setErrorState(M.getLoadError(error));
  }
}
function renderProducerBadges(producerNames, maxVisible = 4) {
  const names = ensureArray(producerNames).filter(Boolean);

  if (!names.length) {
    return `<span class="text-muted">-</span>`;
  }

  const visibleNames = names.slice(0, maxVisible);
  const hiddenCount = Math.max(0, names.length - visibleNames.length);
  const fullProducerList = names.join(", ");

  return `
    <div
      class="order-history-producers-list"
      title="${escapeHtml(fullProducerList)}"
    >
      ${visibleNames
        .map(
          (name) => `
            <span class="badge rounded-pill text-bg-light border order-history-producer-badge">
              ${escapeHtml(name)}
            </span>
          `,
        )
        .join("")}

      ${
        hiddenCount > 0
          ? `
            <span class="badge rounded-pill text-bg-light border order-history-producer-badge">
              +${hiddenCount} more
            </span>
          `
          : ""
      }
    </div>
  `;
}

function renderOrdersTable(orders) {
  const wrapper = document.getElementById("orderTableWrapper");
  const tbody = document.getElementById("orderTableBody");

  if (!wrapper || !tbody) return;

  tbody.innerHTML = orders
    .map(
      (order) => `
    <tr>
      <td><strong>${escapeHtml(order.order_number)}</strong></td>
      <td>${formatDate(order.order_date)}</td>

      <td class="order-history-producers-cell">
        ${renderProducerBadges(order.producer_names)}
      </td>

      <td>${formatMoney(order.total)}</td>

      <td>
        <span class="badge ${getStatusBadgeClass(order.order_status)}">
          ${escapeHtml(order.order_status)}
        </span>
      </td>

      <td class="text-end order-history-actions-cell">
        <div class="order-history-actions">
          <button
            type="button"
            class="btn btn-sm btn-primary order-history-action-btn"
            data-action="view-details"
            data-order-id="${escapeHtml(order.id)}"
          >
            ${M.viewDetailsButton}
          </button>


          ${getReorderButtonHtml(order, "btn-sm order-history-action-btn")}

          ${getReorderButtonHtml(
            order.id,
            order.order_status,
            "btn-sm order-history-action-btn",
          )}
        </div>
      </td>
    </tr>
  `,
    )
    .join("");

  document.getElementById("orderListLoading")?.classList.add("d-none");
  wrapper.classList.remove("d-none");
}

function formatAddress(address) {
  if (!address) {
    return `<div class="text-muted">${M.addressUnavailable}</div>`;
  }

  const lines = [
    address.line_1,
    address.line_2,
    [address.city, address.postcode].filter(Boolean).join(" "),
  ].filter(Boolean);

  if (!lines.length) {
    return `<div class="text-muted">${M.addressUnavailable}</div>`;
  }

  return lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

function renderOrderSummary(order) {
  return `
    <div class="row g-3 mb-4 order-detail-summary">
      <div class="col-12 col-sm-6 col-lg-3">
        <div class="order-detail-summary-card border rounded p-3 h-100">
          <div class="small text-muted">${M.orderNumberLabel}</div>
          <div
            class="fw-semibold order-detail-summary-value order-detail-order-number"
            title="${escapeHtml(order.order_number)}"
          >
            ${escapeHtml(order.order_number)}
          </div>
        </div>
      </div>

      <div class="col-12 col-sm-6 col-lg-3">
        <div class="order-detail-summary-card border rounded p-3 h-100">
          <div class="small text-muted">${M.orderDateLabel}</div>
          <div class="fw-semibold order-detail-summary-value">
            ${formatDate(order.order_date)}
          </div>
        </div>
      </div>

      <div class="col-12 col-sm-6 col-lg-3">
        <div class="order-detail-summary-card border rounded p-3 h-100">
          <div class="small text-muted">${M.statusLabel}</div>
          <div class="fw-semibold order-detail-summary-value">
            ${escapeHtml(order.status || order.order_status || "-")}
          </div>
        </div>
      </div>

      <div class="col-12 col-sm-6 col-lg-3">
        <div class="order-detail-summary-card border rounded p-3 h-100">
          <div class="small text-muted">${M.paymentLabel}</div>
          <div class="fw-semibold order-detail-summary-value">
            ${escapeHtml(order.payment_method_display || M.notAvailable)}
          </div>
        </div>
      </div>

      ${
        order.status_note
          ? `
      <div class="col-12">
        <div class="alert alert-info mb-0">
  ${escapeHtml(order.status_note)}
</div>
      </div>
    `
          : ""
      }
    </div>
  `;
}
function getReviewActionLabel(action) {
  return action?.label || "Write Review";
}

function getReviewedBadgeLabel() {
  return "Reviewed";
}

function buildWriteReviewPayloadFromAction(item) {
  const action = item?.review_action || {};
  const payload = action.payload || {};

  return {
    orderId: payload.order_id || "",
    orderItemId: payload.order_item_id || "",
    productId: payload.product_id || "",
    productName: item?.product_name || "",
    producerName: item?.producer || "",
    quantity: item?.quantity || 0,
    paidUnitPrice: item?.paid_unit_price || null,
  };
}

function renderReviewActionCell(item) {
  const action = item?.review_action;

  if (!action) {
    return `<span class="text-muted">-</span>`;
  }

  const payload = buildWriteReviewPayloadFromAction(item);
  const label = escapeHtml(getReviewActionLabel(action));

  if (action.already_reviewed) {
    return `
      <span
        class="badge text-bg-light border"
        title="${escapeHtml(action.reason || getReviewedBadgeLabel())}"
      >
        ${escapeHtml(getReviewedBadgeLabel())}
      </span>
    `;
  }

  if (action.eligible) {
    return `
      <button
        type="button"
        class="btn btn-sm btn-primary"
        data-action="write-review"
        data-order-id="${escapeHtml(payload.orderId)}"
        data-order-item-id="${escapeHtml(payload.orderItemId)}"
        data-product-id="${escapeHtml(payload.productId)}"
        data-product-name="${escapeHtml(payload.productName)}"
        data-producer-name="${escapeHtml(payload.producerName)}"
        title="${escapeHtml(action.reason || getReviewActionLabel(action))}"
      >
        ${label}
      </button>
    `;
  }

  return `
    <button
      type="button"
      class="btn btn-sm btn-primary"
      disabled
      title="${escapeHtml(action.reason || "Review is not available yet.")}"
      aria-disabled="true"
    >
      ${label}
    </button>
  `;
}

function buildReviewAddUrl(payload) {
  const params = new URLSearchParams({
    order_id: String(payload.orderId || ""),
    order_item_id: String(payload.orderItemId || ""),
    product_id: String(payload.productId || ""),
    next: `${window.location.pathname}${window.location.search}${window.location.hash}`,
    popup: "1",
  });

  return `${REVIEW_ADD_PAGE_URL}?${params.toString()}`;
}

function handleWriteReviewClick(button) {
  const payload = {
    orderId: button.dataset.orderId || "",
    orderItemId: button.dataset.orderItemId || "",
    productId: button.dataset.productId || "",
    productName: button.dataset.productName || "",
    producerName: button.dataset.producerName || "",
  };

  const reviewUrl = buildReviewAddUrl(payload);

  const popup = window.open(
    reviewUrl,
    "write-review",
    "popup=yes,width=760,height=860,resizable=yes,scrollbars=yes",
  );

  if (!popup) {
    window.location.assign(reviewUrl);
  }
}

function isOrderItemFullyCancelled(item) {
  const originalQuantity = Number(item?.quantity ?? 0);
  const cancelledQuantity = Number(item?.cancelled_quantity ?? 0);
  const activeQuantity = Number(
    item?.active_quantity ?? Math.max(originalQuantity - cancelledQuantity, 0),
  );

  const status = normaliseStatus(item?.status_key || item?.status || "");

  return (
    status === "can" ||
    status === "cancelled" ||
    (originalQuantity > 0 && cancelledQuantity >= originalQuantity) ||
    (activeQuantity <= 0 && cancelledQuantity > 0)
  );
}

function isOrderItemPartiallyCancelled(item) {
  const originalQuantity = Number(item?.quantity ?? 0);
  const cancelledQuantity = Number(item?.cancelled_quantity ?? 0);

  return (
    cancelledQuantity > 0 &&
    originalQuantity > 0 &&
    cancelledQuantity < originalQuantity
  );
}

function getOrderItemRowClass(item) {
  return isOrderItemFullyCancelled(item)
    ? "order-detail-item-row order-detail-item-row-cancelled"
    : "order-detail-item-row";
}

function renderOrderItemStatus(item) {
  if (isOrderItemFullyCancelled(item)) {
    return `
      <div class="mt-1">
        <span class="badge text-bg-secondary">Cancelled</span>
      </div>
    `;
  }

  if (isOrderItemPartiallyCancelled(item)) {
    return `
      <div class="mt-1">
        <span class="badge text-bg-warning">Partly cancelled</span>
      </div>
    `;
  }

  if (item.status) {
    return `<div class="small text-muted mt-1">${escapeHtml(item.status)}</div>`;
  }

  return "";
}

function renderOrderItemQuantityCell(item) {
  const originalQuantity = Number(item?.quantity ?? 0);
  const cancelledQuantity = Number(item?.cancelled_quantity ?? 0);
  const activeQuantity = Number(
    item?.active_quantity ?? Math.max(originalQuantity - cancelledQuantity, 0),
  );

  if (isOrderItemFullyCancelled(item)) {
    return `
      <div class="fw-semibold text-muted">Cancelled</div>
      <div class="small text-muted">
        Original quantity: ${escapeHtml(originalQuantity)}
      </div>
    `;
  }

  if (isOrderItemPartiallyCancelled(item)) {
    return `
      <div class="fw-semibold">${escapeHtml(activeQuantity)}</div>
      <div class="small text-warning-emphasis">
        ${escapeHtml(cancelledQuantity)} cancelled
      </div>
      <div class="small text-muted">
        Original quantity: ${escapeHtml(originalQuantity)}
      </div>
    `;
  }

  return `<div class="fw-semibold">${escapeHtml(activeQuantity)}</div>`;
}

function renderOrderItemActions(order, item) {
  if (isOrderItemFullyCancelled(item)) {
    return `
      <span class="badge text-bg-light border order-detail-item-disabled-badge">
        No action available
      </span>
    `;
  }

  return `
    <div class="d-flex gap-2 justify-content-end flex-wrap">
      ${getCustomerCancelItemButtonHtml(order, item)}
      ${renderReviewActionCell(item)}
    </div>
  `;
}
function renderItemsSection(order) {
  const items = order?.items || [];

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.itemsHeading}</h6>
      <div class="table-responsive">
        <table class="table table-bordered align-middle order-detail-items-table">
          <thead class="table-light">
            <tr>
              <th>${M.productLabel}</th>
              <th>${M.producerLabel}</th>
              <th>${M.quantityLabel}</th>
              <th>${M.unitPriceLabel}</th>
              <th class="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${(items || [])
              .map((item) => {
                const fullyCancelled = isOrderItemFullyCancelled(item);

                return `
                  <tr
                    class="${escapeHtml(getOrderItemRowClass(item))}"
                    ${fullyCancelled ? 'aria-disabled="true"' : ""}
                  >
                    <td>
                      <div class="fw-semibold order-detail-item-product-name">
                        ${escapeHtml(item.product_name)}
                      </div>
                      ${renderOrderItemStatus(item)}
                    </td>

                    <td>${escapeHtml(item.producer)}</td>

                    <td>
                      ${renderOrderItemQuantityCell(item)}
                    </td>

                    <td>
                      ${formatMoney(item.paid_unit_price)}
                    </td>

                    <td class="text-end">
                      ${renderOrderItemActions(order, item)}
                    </td>
                  </tr>
                `;
              })
              .join("")}
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
        <h6 class="mb-3">${M.fulfilmentHeading}</h6>
        <div class="border rounded p-3 text-muted">
          ${M.fulfilmentUnavailable}
        </div>
      </div>
    `;
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.fulfilmentHeading}</h6>
      <div class="row g-3">
        ${(producerBreakdown || [])
          .map((summary) => {
            const isCollection = (summary.delivery_or_collection || "")
              .toLowerCase()
              .includes("collection");
            const date = isCollection
              ? summary.collection_date
              : summary.delivery_date;
            const timeSlot = isCollection
              ? summary.collection_time_slot
              : summary.delivery_time_slot;
            const address = isCollection
              ? summary.collection_address
              : summary.delivery_address;
            const addressLabel = isCollection
              ? "Collection address"
              : "Delivery address";

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
                    <div class="small text-muted">${M.dateLabel}</div>
                    <div class="fw-semibold">${formatDate(date)}</div>
                  </div>
                  <div class="col-md-4">
                    <div class="small text-muted">${M.timeSlotLabel}</div>
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
          })
          .join("")}
      </div>
    </div>
  `;
}

function renderProducerSection(producerBreakdown) {
  if (!(producerBreakdown || []).length) {
    return `
      <div class="mb-4">
        <h6 class="mb-3">${M.producerDetailsHeading}</h6>
        <div class="border rounded p-3 text-muted">Producer details are not available.</div>
      </div>
    `;
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.producerDetailsHeading}</h6>
      ${(producerBreakdown || [])
        .map(
          (summary) => `
        <div class="card mb-3">
          <div class="card-body">
            <div class="d-flex justify-content-between flex-wrap gap-2 mb-3">
              <div>
                <h6 class="mb-1">${escapeHtml(summary.producer_name || "Unknown producer")}</h6>
                <div class="small text-muted">${escapeHtml(summary.status || "-")}</div>
              </div>
              <div class="text-end">
                <div class="small text-muted">${M.subtotalLabel}</div>
                <div class="fw-semibold">${formatMoney(summary.subtotal)}</div>
              </div>
            </div>

            <div class="row g-3">
              <div class="col-md-3">
                <div class="small text-muted">${M.fulfilmentTypeLabel}</div>
                <div>${escapeHtml(summary.delivery_or_collection || "-")}</div>
              </div>
              <div class="col-md-3">
                <div class="small text-muted">${M.vatLabel}</div>
                <div>${formatMoney(summary.vat_total)}</div>
              </div>
              <div class="col-md-6">
                <div class="small text-muted">${M.instructionsLabel}</div>
                <div>${escapeHtml(summary.special_instructions || "-")}</div>
              </div>
            </div>
          </div>
        </div>
      `,
        )
        .join("")}
    </div>
  `;
}

function renderOrderFooter(order) {
  const displayTotal =
    order.display_total_price ?? order.active_total_price ?? order.total_price;

  const originalTotal = order.original_total_price ?? order.total_price;

  const cancelledTotal = Number(order.cancelled_total_price || 0);
  const hasCancelledValue = cancelledTotal > 0;

  const displayLabel = order.display_total_label || M.totalPaidLabel;

  return `
    <div class="border rounded p-3 d-flex justify-content-between align-items-center flex-wrap gap-3">
      <div>
        <div class="small text-muted">${escapeHtml(displayLabel)}</div>
        <div class="fs-5 fw-bold">${formatMoney(displayTotal)}</div>

        ${
          hasCancelledValue
            ? `
              <div class="small text-muted mt-1">
                Original order total: ${formatMoney(originalTotal)}
              </div>
              <div class="small text-muted">
                Cancelled value removed: ${formatMoney(cancelledTotal)}
              </div>
              ${
                order.display_total_note
                  ? `
                    <div class="small text-muted">
                      ${escapeHtml(order.display_total_note)}
                    </div>
                  `
                  : ""
              }
            `
            : ""
        }
      </div>

      <div class="d-flex gap-2">
        ${getCustomerCancelButtonHtml(order)}
        ${getReorderButtonHtml(order)}
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
      throw await buildApiErrorFromResponse(response, M.detailLoadFailed);
    }

    const order = await response.json();

    if (content) {
      content.innerHTML = `
        ${renderOrderSummary(order)}
        ${renderFulfilmentSection(order.producer_breakdown || [])}
        ${renderItemsSection(order)}
        ${renderProducerSection(order.producer_breakdown || [])}
        ${renderOrderFooter(order)}
      `;
      content.classList.remove("d-none");
    }

    if (loading) loading.classList.add("d-none");
  } catch (error) {
    if (loading) loading.classList.add("d-none");
    if (errorBox) {
      errorBox.textContent = M.getDetailLoadError(error);
      errorBox.classList.remove("d-none");
    }
  }
}

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

  if (
    maxAvailable === null ||
    maxAvailable === undefined ||
    maxAvailable === ""
  ) {
    return parsed;
  }

  const max = Math.max(1, parseInt(maxAvailable, 10) || 1);
  return Math.min(parsed, max);
}

function buildLookupByOrderItemId(items) {
  const lookup = new Map();

  ensureArray(items).forEach((item) => {
    if (
      item &&
      item.order_item_id !== null &&
      item.order_item_id !== undefined
    ) {
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
    available_quantity:
      item.available_quantity ??
      item.added_quantity ??
      item.requested_quantity ??
      null,
    current_price: item.current_price,
    pricing: item.pricing || null,
    match_basis: item.match_basis || "same_product",
    recommendation_badge: item.recommendation_badge || "",
    source_label: M.originalBadge,
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
    recommendation_badge: item.recommendation_badge || "",
    source_label: M.alternativeProducerBadge,
  };
}

function createSkipOption(groupId) {
  return {
    key: `skip:${groupId}`,
    action: "skip",
    product_id: null,
    product_name: M.skipItemTitle,
    producer_id: null,
    producer_name: "",
    inventory_id: null,
    available_quantity: null,
    current_price: 0,
    pricing: null,
    match_basis: "",
    source_label: M.skipLabel,
  };
}

function buildReorderPlannerState(orderId, preview) {
  const quantityAdjustedLookup = buildLookupByOrderItemId(
    preview.quantity_adjusted_items,
  );
  const priceChangedLookup = buildLookupByOrderItemId(
    preview.price_changed_items,
  );
  const producerChangedLookup = buildLookupByOrderItemId(
    preview.producer_changed_items,
  );

  const groups = [];

  ensureArray(preview.addable_items).forEach((item, index) => {
    const groupId = String(item.order_item_id ?? `available-${index}`);
    const originalRequestedQuantity = toNumber(
      item.requested_quantity ?? item.added_quantity,
      1,
    );

    const originalOption = createOptionFromAddableItem(item);
    const suggestedOptions = ensureArray(item.suggested_items).map(
      createOptionFromSuggestedItem,
    );

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
      options: [originalOption, ...suggestedOptions, createSkipOption(groupId)],
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
    const suggestedOptions = ensureArray(item.suggested_items).map(
      createOptionFromSuggestedItem,
    );
    const hasSuggestions = suggestedOptions.length > 0;
    const selectedOption = hasSuggestions
      ? suggestedOptions[0]
      : createSkipOption(groupId);

    groups.push({
      groupId,
      orderItemId: item.order_item_id ?? null,
      kind: hasSuggestions ? "needs-choice" : "unavailable",
      original: {
        product_name: item.product_name,
        producer_name: item.producer_name || "",
        requested_quantity: originalRequestedQuantity,
        reason: M.getReorderItemReason(item),
      },
      selectedOptionKey: selectedOption.key,
      quantity: hasSuggestions
        ? clampQuantity(
            originalRequestedQuantity,
            selectedOption.available_quantity,
          )
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
  return (
    reorderPlannerState.groups.find(
      (group) => String(group.groupId) === String(groupId),
    ) || null
  );
}

function getSelectedOption(group) {
  if (!group) return null;
  return (
    group.options.find((option) => option.key === group.selectedOptionKey) ||
    null
  );
}

function getTierMinQuantity(tier) {
  return toNumber(tier?.min_quantity, 0);
}

function getTierUnitPrice(tier, fallback = 0) {
  return toNumber(tier?.unit_price, fallback);
}

function getApplicableKnownWholesaleTier(option, quantity) {
  const wholesale = option.pricing?.wholesale || null;
  const matchedTier = wholesale?.matched_tier || null;
  const nextTier = wholesale?.next_tier || null;

  if (nextTier && quantity >= getTierMinQuantity(nextTier)) {
    return nextTier;
  }

  if (matchedTier && quantity >= getTierMinQuantity(matchedTier)) {
    return matchedTier;
  }

  return null;
}

function getPricingState(option, quantity) {
  const pricing = option.pricing || {};
  const surplus = pricing.surplus || {};
  const wholesale = pricing.wholesale || {};

  const baseUnitPrice = toNumber(
    pricing.base_unit_price ?? option.current_price,
    0,
  );
  const effectiveUnitPrice = toNumber(
    pricing.effective_unit_price ?? option.current_price,
    baseUnitPrice,
  );

  const applicableTier = getApplicableKnownWholesaleTier(option, quantity);
  const tierUnitPrice = applicableTier
    ? getTierUnitPrice(applicableTier, effectiveUnitPrice)
    : effectiveUnitPrice;

  const appliedUnitPrice = Math.min(effectiveUnitPrice, tierUnitPrice);
  const wholesaleActive =
    Boolean(applicableTier) && tierUnitPrice < effectiveUnitPrice;
  const surplusActive = Boolean(surplus.is_active);

  let compareUnitPrice = null;
  if (wholesaleActive) {
    compareUnitPrice = effectiveUnitPrice;
  } else if (surplusActive && baseUnitPrice > effectiveUnitPrice) {
    compareUnitPrice = baseUnitPrice;
  }

  const savingsPerUnit =
    compareUnitPrice !== null
      ? Math.max(0, compareUnitPrice - appliedUnitPrice)
      : 0;

  const upcomingTier =
    wholesale?.next_tier && quantity < getTierMinQuantity(wholesale.next_tier)
      ? wholesale.next_tier
      : null;

  return {
    baseUnitPrice,
    effectiveUnitPrice,
    appliedUnitPrice,
    compareUnitPrice,
    savingsPerUnit,
    surplusActive,
    surplusDiscountPercentage: surplus.discount_percentage,
    wholesale,
    wholesaleActive,
    applicableTier,
    upcomingTier,
  };
}

function renderPriceCutBadge(pricingState) {
  if (pricingState.wholesaleActive) {
    return `
      <span class="badge rounded-pill bg-warning text-dark">
        ${M.wholesaleBadge} price
      </span>
    `;
  }

  if (pricingState.surplusActive) {
    if (pricingState.surplusDiscountPercentage) {
      return `
        <span class="badge rounded-pill bg-danger">
          ${escapeHtml(pricingState.surplusDiscountPercentage)}% off
        </span>
      `;
    }

    return `
      <span class="badge rounded-pill bg-danger">
        ${M.surplusBadge} price
      </span>
    `;
  }

  if (pricingState.savingsPerUnit > 0) {
    return `
      <span class="badge rounded-pill bg-danger">
        Save ${escapeHtml(formatMoney(pricingState.savingsPerUnit))}
      </span>
    `;
  }

  return "";
}

function renderPriceStack(option, quantity, extraClass = "") {
  const pricingState = getPricingState(option, quantity);

  return `
    <div class="${escapeHtml(extraClass)}">
      <div class="d-flex align-items-center justify-content-md-end gap-2 flex-wrap">
        <div class="fw-semibold">${formatMoney(pricingState.appliedUnitPrice)}</div>

        ${
          pricingState.compareUnitPrice !== null
            ? `
              <div class="small text-muted text-decoration-line-through">
                ${formatMoney(pricingState.compareUnitPrice)}
              </div>
            `
            : ""
        }

        ${renderPriceCutBadge(pricingState)}
      </div>
    </div>
  `;
}
function getPlannerStats() {
  if (!reorderPlannerState) {
    return {
      selectedCount: 0,
      skippedCount: 0,
      estimatedSubtotal: 0,
      estimatedCompareSubtotal: 0,
      estimatedSavings: 0,
      actionableCount: 0,
    };
  }

  return reorderPlannerState.groups.reduce(
    (stats, group) => {
      const selectedOption = getSelectedOption(group);

      if (!selectedOption || selectedOption.action === "skip") {
        stats.skippedCount += 1;
        return stats;
      }

      const quantity = clampQuantity(
        group.quantity,
        selectedOption.available_quantity,
      );
      const pricingState = getPricingState(selectedOption, quantity);

      stats.selectedCount += 1;
      stats.actionableCount += 1;
      stats.estimatedSubtotal += quantity * pricingState.appliedUnitPrice;
      stats.estimatedCompareSubtotal +=
        quantity *
        (pricingState.compareUnitPrice !== null
          ? pricingState.compareUnitPrice
          : pricingState.appliedUnitPrice);
      stats.estimatedSavings += quantity * pricingState.savingsPerUnit;
      return stats;
    },
    {
      selectedCount: 0,
      skippedCount: 0,
      estimatedSubtotal: 0,
      estimatedCompareSubtotal: 0,
      estimatedSavings: 0,
      actionableCount: 0,
    },
  );
}

function serializeSelectionsFromState() {
  if (!reorderPlannerState) return [];

  return reorderPlannerState.groups
    .map((group) => {
      const selectedOption = getSelectedOption(group);

      if (
        !selectedOption ||
        group.orderItemId === null ||
        group.orderItemId === undefined
      ) {
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
        quantity: clampQuantity(
          group.quantity,
          selectedOption.available_quantity,
        ),
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
    const fallbackQuantity =
      group.quantity || group.original.requested_quantity || 1;
    group.quantity = clampQuantity(
      fallbackQuantity,
      selectedOption.available_quantity,
    );
  }

  updateReorderPlannerUI();
}

function updateGroupQuantity(groupId, rawValue) {
  const group = getGroupById(groupId);
  if (!group) return;

  const selectedOption = getSelectedOption(group);
  if (!selectedOption || selectedOption.action === "skip") return;

  const requestedQuantity = toPositiveInteger(rawValue) || 1;
  const availableQuantity = toPositiveInteger(
    selectedOption.available_quantity,
  );

  const toastMessage = getQuantityLimitToastMessage(
    group,
    selectedOption,
    requestedQuantity,
  );

  if (toastMessage) {
    showOrderToast(toastMessage, {
      title: M.cartTitle,
      variant: "danger",
      delay: 3000,
    });
  }

  group.quantity = availableQuantity
    ? Math.min(requestedQuantity, availableQuantity)
    : requestedQuantity;

  updateReorderPlannerUI();
}

function changeGroupQuantity(groupId, delta) {
  const group = getGroupById(groupId);
  if (!group) return;

  const selectedOption = getSelectedOption(group);
  if (!selectedOption || selectedOption.action === "skip") return;

  const current = toPositiveInteger(group.quantity) || 1;
  const requestedQuantity = Math.max(1, current + delta);
  const availableQuantity = toPositiveInteger(
    selectedOption.available_quantity,
  );

  const toastMessage = getQuantityLimitToastMessage(
    group,
    selectedOption,
    requestedQuantity,
  );

  if (toastMessage) {
    showOrderToast(toastMessage, {
      title: M.cartTitle,
      variant: "danger",
      delay: 3000,
    });
  }

  group.quantity = availableQuantity
    ? Math.min(requestedQuantity, availableQuantity)
    : requestedQuantity;

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

  const groups = reorderPlannerState?.groups || [];
  const needsReviewCount = groups.filter(
    (group) => group.kind === "needs-choice",
  ).length;
  const unavailableCount = groups.filter(
    (group) => group.kind === "unavailable",
  ).length;
  const alternativeCount = groups.reduce((count, group) => {
    return (
      count +
      group.options.filter((option) => option.action === "replace").length
    );
  }, 0);

  const helperNotes = [];

  if (needsReviewCount > 0) {
    helperNotes.push(M.needsReviewSummary(needsReviewCount));
  }

  if (alternativeCount > 0) {
    helperNotes.push(M.alternativeOptionsSummary(alternativeCount));
  }

  if (unavailableCount > 0) {
    helperNotes.push(M.unavailableSummary(unavailableCount));
  }

  const helperSummary = helperNotes.length
    ? helperNotes.join(" • ")
    : M.allAvailableSelectedSummary;

  return `
    <div class="border rounded p-3 mb-4 bg-light">
      <div class="row g-3 align-items-start">
        <div class="col-md-7">
          <div class="fw-semibold mb-1">${M.reviewItemsTitle}</div>

          <div class="small text-muted">
            ${M.reviewItemsBody}
          </div>

          <div class="small text-muted mt-2">
            ${escapeHtml(helperSummary)}
          </div>

          <div class="d-flex flex-wrap gap-2 mt-3">
            <span class="badge text-bg-light border">
              ${escapeHtml(M.selectedBadge(stats.selectedCount))}
            </span>

            <span class="badge text-bg-light border">
              ${escapeHtml(M.skippedBadge(stats.skippedCount))}
            </span>

            ${
              needsReviewCount > 0
                ? `
                  <span class="badge text-bg-light border">
                    ${escapeHtml(M.needsReviewBadge(needsReviewCount))}
                  </span>
                `
                : ""
            }
          </div>
        </div>

        <div class="col-md-5 text-md-end">
          <div class="small text-muted">${M.estimatedTotalLabel}</div>
          <div class="fs-4 fw-bold">${formatMoney(stats.estimatedSubtotal)}</div>

          ${
            stats.estimatedSavings > 0
              ? `
                <div class="mt-2">
                  <span class="badge rounded-pill bg-danger">
                    ${M.saveAmount(escapeHtml(formatMoney(stats.estimatedSavings)))}
                  </span>
                </div>
              `
              : ""
          }

          ${
            stats.estimatedCompareSubtotal > stats.estimatedSubtotal
              ? `
                <div class="small text-muted mt-2">
                  ${M.regularTotalLabel}
                  <span class="text-decoration-line-through">
                    ${formatMoney(stats.estimatedCompareSubtotal)}
                  </span>
                </div>
              `
              : ""
          }
        </div>
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
  const value = String(matchBasis || "")
    .replaceAll("_", " ")
    .trim();
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderOptionBadges(group, option) {
  const badges = [];

  if (group.kind === "available" && option.action === "keep") {
    badges.push(`
      <span class="badge rounded-pill text-bg-light border me-1 mb-1">
        ${M.originalBadge}
      </span>
    `);
  }

  if (option.action === "replace") {
    badges.push(`
      <span class="badge rounded-pill text-bg-light border me-1 mb-1">
        ${M.alternativeProducerBadge}
      </span>
    `);
  }

  if (option.action === "replace" && option.match_basis) {
    badges.push(`
      <span class="badge rounded-pill text-bg-light border me-1 mb-1">
        ${escapeHtml(M.matchBadge(renderMatchBasisLabel(option.match_basis)))}
      </span>
    `);
  }
  if (option.recommendation_badge === "trending") {
    badges.push(`
      <span class="badge rounded-pill bg-success me-1 mb-1">
        ${escapeHtml(M.trendingBadge)}
      </span>
    `);
  }

  if (option.recommendation_badge === "new") {
    badges.push(`
      <span class="badge rounded-pill bg-primary me-1 mb-1">
        ${escapeHtml(M.newBadge)}
      </span>
    `);
  }

  if (option.pricing?.surplus?.is_active) {
    badges.push(`
      <span class="badge rounded-pill bg-danger me-1 mb-1">
        ${M.surplusBadge}
      </span>
    `);
  }

  if (option.pricing?.wholesale?.has_wholesale_tiers) {
    badges.push(`
      <span class="badge rounded-pill bg-warning text-dark me-1 mb-1">
        ${M.wholesaleBadge}
      </span>
    `);
  }

  return badges.join("");
}
function renderQuantityAdjustmentNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-warning-emphasis mt-2">
      ${escapeHtml(M.requestedAvailableNow(signal.requested_quantity, signal.added_quantity, signal.reason || ""))}
    </div>
  `;
}

function renderPriceChangeNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-primary mt-2">
      ${escapeHtml(M.priceChanged(formatMoney(signal.original_price), formatMoney(signal.current_price)))}
    </div>
  `;
}

function renderProducerChangeNotice(signal) {
  if (!signal) return "";

  return `
    <div class="small text-secondary mt-2">
      ${escapeHtml(M.producerChanged(signal.original_producer_name, signal.current_producer_name))}
    </div>
  `;
}

function renderWholesaleNotice(option, quantity) {
  const pricingState = getPricingState(option, quantity);
  const wholesale = option.pricing?.wholesale || null;

  if (!wholesale?.has_wholesale_tiers) {
    return "";
  }

  if (pricingState.wholesaleActive) {
    if (pricingState.upcomingTier) {
      return `
        <div class="small text-muted mt-2">
          <span class="fw-semibold text-dark">${M.wholesaleActive}</span>
          ${M.wholesaleActiveNextTier(escapeHtml(pricingState.upcomingTier.min_quantity), formatMoney(pricingState.upcomingTier.unit_price))}
        </div>
      `;
    }

    return `
      <div class="small text-muted mt-2">
        <span class="fw-semibold text-dark">${M.wholesaleActive}</span>
        ${M.wholesaleActiveQualified}
      </div>
    `;
  }

  if (pricingState.upcomingTier) {
    const difference = getTierMinQuantity(pricingState.upcomingTier) - quantity;

    return `
      <div class="small text-muted mt-2">
        ${M.wholesaleUnlock(escapeHtml(pricingState.upcomingTier.min_quantity), formatMoney(pricingState.upcomingTier.unit_price), escapeHtml(difference))}
      </div>
    `;
  }

  return "";
}

function renderSurplusNotice(option, quantity) {
  const pricingState = getPricingState(option, quantity);

  if (!pricingState.surplusActive) {
    return "";
  }

  if (pricingState.wholesaleActive) {
    return `
      <div class="small text-muted mt-2">
        ${M.surplusBetterPrice}
      </div>
    `;
  }

  return `
    <div class="small text-muted mt-2">
      ${M.surplusApplied}
    </div>
  `;
}

function renderQuantityControls(group, option) {
  const quantity = clampQuantity(group.quantity, option.available_quantity);
  const minusDisabled = quantity <= 1 ? "disabled" : "";
  const plusDisabled = "";

  const pricingState = getPricingState(option, quantity);
  const lineAppliedTotal = pricingState.appliedUnitPrice * quantity;
  const lineCompareTotal =
    pricingState.compareUnitPrice !== null
      ? pricingState.compareUnitPrice * quantity
      : null;

  return `
    <div class="mt-3 pt-3 border-top">
      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label small text-muted mb-1">${M.quantityLabel}</label>

          <div class="input-group">
            <button
              type="button"
              class="btn btn-primary"
              data-action="reorder-qty-minus"
              data-group-id="${escapeHtml(group.groupId)}"
              ${minusDisabled}
            >
              −
            </button>

            <input
              type="number"
              min="1"
              ${
                option.available_quantity !== null &&
                option.available_quantity !== undefined
                  ? `max="${escapeHtml(option.available_quantity)}"`
                  : ""
              }
              class="form-control text-center js-reorder-qty-input"
              data-group-id="${escapeHtml(group.groupId)}"
              value="${escapeHtml(quantity)}"
            >

            <button
              type="button"
              class="btn btn-primary"
              data-action="reorder-qty-plus"
              data-group-id="${escapeHtml(group.groupId)}"
              ${plusDisabled}
            >
              +
            </button>
          </div>

          <div class="small text-muted mt-2">
            ${M.availableNow(escapeHtml(option.available_quantity ?? M.notSpecified))}
          </div>
        </div>

        <div class="col-md-8">
          <div class="border rounded p-3 bg-light">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
              <div>
                <div class="small text-muted">${M.currentUnitPriceLabel}</div>
                <div class="d-flex align-items-center gap-2 flex-wrap mt-1">
                  <div class="fs-4 fw-bold">${formatMoney(pricingState.appliedUnitPrice)}</div>

                  ${
                    pricingState.compareUnitPrice !== null
                      ? `
                        <div class="small text-muted text-decoration-line-through">
                          ${formatMoney(pricingState.compareUnitPrice)}
                        </div>
                      `
                      : ""
                  }

                  ${renderPriceCutBadge(pricingState)}
                </div>

                <div class="small text-muted mt-1">
                  ${M.basePriceLabel}: ${formatMoney(pricingState.baseUnitPrice)} each
                </div>

                ${renderWholesaleNotice(option, quantity)}
                ${renderSurplusNotice(option, quantity)}
              </div>

              <div class="text-md-end">
                <div class="small text-muted">${M.lineTotalLabel}</div>
                <div class="fw-semibold fs-5">${formatMoney(lineAppliedTotal)}</div>

                ${
                  lineCompareTotal !== null
                    ? `
                      <div class="small text-muted">
                        ${M.wasLabel}
                        <span class="text-decoration-line-through">
                          ${formatMoney(lineCompareTotal)}
                        </span>
                      </div>
                    `
                    : ""
                }

                ${
                  pricingState.savingsPerUnit > 0
                    ? `
                      <div class="small text-success mt-1">
                        ${M.saveAmount(formatMoney(pricingState.savingsPerUnit * quantity))}
                      </div>
                    `
                    : ""
                }
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderOptionCard(group, option) {
  const selected = option.key === group.selectedOptionKey;
  const inputId = `reorder-option-${makeDomSafeId(group.groupId)}-${makeDomSafeId(option.key)}`;
  const cardClass = selected ? "border-primary shadow-sm" : "border";
  const previewQty = selected
    ? group.quantity
    : group.original.requested_quantity;

  if (group.kind === "unavailable" && option.action === "skip") {
    return `
      <div class="border rounded p-3 bg-light">
        <div class="fw-semibold">${M.noAlternativeTitle}</div>
        <div class="small text-muted mt-1">
          ${M.noAlternativeBody}
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
                ${
                  option.producer_name
                    ? `${escapeHtml(option.producer_name)}`
                    : ""
                }
              </div>

              <div class="mt-2">
                ${renderOptionBadges(group, option)}
              </div>

              ${
                option.action !== "skip"
                  ? `
                    <div class="small text-muted mt-2">
                      ${M.availableNow(escapeHtml(option.available_quantity ?? M.notSpecified))}
                    </div>
                  `
                  : `
                    <div class="small text-muted mt-2">
                      ${M.availableWithChoiceBody}
                    </div>
                  `
              }
            </div>

            <div class="text-md-end">
              ${
                option.action === "skip"
                  ? `<div class="fw-semibold">Skip</div>`
                  : `
                    ${renderPriceStack(option, previewQty)}
                    <div class="small text-muted">per unit</div>
                  `
              }
            </div>
          </div>
        </label>
      </div>

      ${selected && option.action !== "skip" ? renderQuantityControls(group, option) : ""}
    </div>
  `;
}

function renderPlannerGroup(group) {
  const selectedOption = getSelectedOption(group);
  const alternativeCount = Math.max(
    0,
    group.options.filter((option) => option.action === "replace").length,
  );

  let groupTitle = M.availableToAddTitle;
  let groupSubtitle = M.availableToAddSubtitle;

  if (group.kind === "needs-choice") {
    groupTitle = M.chooseAlternativeTitle;
    groupSubtitle = M.chooseAlternativeSubtitle;
  } else if (group.kind === "unavailable") {
    groupTitle = M.currentlyUnavailableTitle;
    groupSubtitle = M.currentlyUnavailableSubtitle;
  } else if (alternativeCount > 0) {
    groupSubtitle = M.availableWithAlternativesSubtitle;
  }

  const selectedQuantity =
    selectedOption && selectedOption.action !== "skip"
      ? clampQuantity(group.quantity, selectedOption.available_quantity)
      : 0;

  const selectedPricingState =
    selectedOption && selectedOption.action !== "skip"
      ? getPricingState(selectedOption, selectedQuantity)
      : null;

  const selectedLineTotal = selectedPricingState
    ? selectedPricingState.appliedUnitPrice * selectedQuantity
    : 0;

  return `
    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-3 align-items-start mb-3">
          <div class="col-md-7">
            <div class="small text-muted">${escapeHtml(groupTitle)}</div>
            <h6 class="mb-1">${escapeHtml(group.original.product_name)}</h6>

            <div class="small text-muted">
              ${
                group.original.producer_name
                  ? `${escapeHtml(group.original.producer_name)} · `
                  : ""
              }
              ${M.originallyOrdered(escapeHtml(group.original.requested_quantity))}
            </div>

            <div class="small text-muted mt-1">${escapeHtml(groupSubtitle)}</div>

            ${
              group.original.reason
                ? `<div class="small text-danger mt-1">${M.requestedReasonLabel}: ${escapeHtml(group.original.reason)}</div>`
                : ""
            }

            ${renderQuantityAdjustmentNotice(group.signals.quantityAdjusted)}
            ${renderPriceChangeNotice(group.signals.priceChanged)}
            ${renderProducerChangeNotice(group.signals.producerChanged)}
          </div>

          <div class="col-md-5">
            <div class="border rounded p-3 bg-light">
              <div class="small text-muted">${M.selectedNowLabel}</div>

              ${
                selectedOption && selectedOption.action !== "skip"
                  ? `
                    <div class="fw-semibold">${escapeHtml(selectedOption.product_name)}</div>
                    <div class="small text-muted">${escapeHtml(selectedOption.producer_name || "")}</div>
                    <div class="mt-2">
                      ${renderOptionBadges(group, selectedOption)}
                    </div>

                    <div class="d-flex justify-content-between mt-3 small text-muted">
                      <span>${M.quantityLabel}</span>
                      <span>${escapeHtml(selectedQuantity)}</span>
                    </div>

                    <div class="d-flex justify-content-between mt-1">
                      <span class="small text-muted">${M.totalLabel}</span>
                      <span class="fw-semibold">${formatMoney(selectedLineTotal)}</span>
                    </div>

                    ${
                      selectedPricingState &&
                      selectedPricingState.savingsPerUnit > 0
                        ? `
                          <div class="mt-2">
                            <span class="badge rounded-pill bg-danger">
                              Save ${escapeHtml(formatMoney(selectedPricingState.savingsPerUnit * selectedQuantity))}
                            </span>
                          </div>
                        `
                        : ""
                    }
                  `
                  : `
                    <div class="fw-semibold">${M.skipItemTitle}</div>
                    <div class="small text-muted mt-1">${M.skipItemBody}</div>
                  `
              }
            </div>
          </div>
        </div>

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
        M.noReorderableItemsTitle,
        M.noReorderableItemsBody,
        "alert-warning",
      )}
    `;
  }

  const availableGroups = reorderPlannerState.groups.filter(
    (group) => group.kind === "available",
  );
  const needsChoiceGroups = reorderPlannerState.groups.filter(
    (group) => group.kind === "needs-choice",
  );
  const unavailableGroups = reorderPlannerState.groups.filter(
    (group) => group.kind === "unavailable",
  );

  return `
    ${renderPlannerSummaryCard()}

    ${renderPlannerSection(
      M.availableItemsSectionTitle,
      M.availableItemsSectionSubtitle,
      availableGroups,
    )}

    ${renderPlannerSection(
      M.chooseAlternativeItemsSectionTitle,
      M.chooseAlternativeItemsSectionSubtitle,
      needsChoiceGroups,
    )}

    ${renderPlannerSection(
      M.unavailableItemsSectionTitle,
      M.unavailableItemsSectionSubtitle,
      unavailableGroups,
    )}
  `;
}
function getReorderPlannerFooterHtml() {
  const stats = getPlannerStats();

  if (
    !reorderPlannerState ||
    !reorderPlannerState.groups.length ||
    stats.actionableCount === 0
  ) {
    return `
      <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
        ${M.closeButton}
      </button>
    `;
  }

  return `
    <button type="button" class="btn btn-danger" data-bs-dismiss="modal">
      ${M.cancelButton}
    </button>
    <button type="button" class="btn btn-primary" id="confirmReorderBtn">
      ${M.confirmButton}
    </button>
  `;
}

function updateReorderPlannerUI() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  if (title) title.textContent = M.previewTitle;
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

  if (title) title.textContent = M.previewTitle;
  if (content) content.innerHTML = "";
  if (footer) {
    footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
        ${M.cancelButton}
      </button>
      <button type="button" class="btn btn-primary" id="confirmReorderBtn" disabled>
        ${M.confirmButton}
      </button>
    `;
  }
}

function setReorderModalLoading() {
  const title = document.getElementById("reorderModalTitle");
  const content = document.getElementById("reorderModalContent");
  const footer = document.getElementById("reorderModalFooter");

  reorderPlannerState = null;

  if (title) title.textContent = M.previewTitle;
  if (content) {
    content.innerHTML = `
      <div class="text-muted">
        ${M.loadingPlannerBody}
      </div>
    `;
  }
  if (footer) {
    footer.innerHTML = `
      <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
        ${M.cancelButton}
      </button>
      <button type="button" class="btn btn-primary" id="confirmReorderBtn" disabled>
        ${M.confirmButton}
      </button>
    `;
  }
}

function setReorderSubmittingState() {
  const confirmBtn = document.getElementById("confirmReorderBtn");
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = M.submittingButton;
  }
}

/* =========================
   REORDER RESULT RENDERING
   ========================= */
/* =========================
   REORDER RESULT RENDERING
   ========================= */

function getResultCounts(result) {
  return {
    added: (result.added_items || []).length,
    unavailable: (result.unavailable_items || []).length,
    quantityAdjusted: (result.quantity_adjusted_items || []).length,
    priceChanged: (result.price_changed_items || []).length,
  };
}

function renderResultSummaryBadges(result) {
  const counts = getResultCounts(result);

  return `
    <div class="d-flex flex-wrap gap-2 mt-3">
      <span class="badge text-bg-light border">
        ${escapeHtml(M.resultBadge(counts.added, M.addedBadgeLabel))}
      </span>

      ${
        counts.unavailable > 0
          ? `
            <span class="badge text-bg-light border">
              ${escapeHtml(M.resultBadge(counts.unavailable, M.unavailableBadgeLabel))}
            </span>
          `
          : ""
      }

      ${
        counts.quantityAdjusted > 0
          ? `
            <span class="badge text-bg-light border">
              ${escapeHtml(M.resultBadge(counts.quantityAdjusted, M.quantityUpdatedBadgeLabel))}
            </span>
          `
          : ""
      }

      ${
        counts.priceChanged > 0
          ? `
            <span class="badge text-bg-light border">
              ${escapeHtml(M.resultBadge(counts.priceChanged, M.priceChangedBadgeLabel))}
            </span>
          `
          : ""
      }
    </div>
  `;
}

function renderAddedItemsSection(items) {
  if (!items || !items.length) {
    return "";
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.addedToCartSectionTitle}</h6>
      ${items
        .map(
          (item) => `
            <div class="border rounded p-3 mb-2">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>

              ${
                item.producer_name
                  ? `
                    <div class="small text-muted mt-1">
                      ${M.producerLine(escapeHtml(item.producer_name))}
                    </div>
                  `
                  : ""
              }

              <div class="small text-muted mt-2">
                ${M.quantityAdded(escapeHtml(item.added_quantity))}
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderUnavailableItemsSection(items) {
  if (!items || !items.length) {
    return "";
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.unavailableItemsResultTitle}</h6>
      ${items
        .map(
          (item) => `
            <div class="border border-danger rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>

              ${
                item.producer_name
                  ? `
                    <div class="small text-muted mt-1">
                      ${M.producerLine(escapeHtml(item.producer_name))}
                    </div>
                  `
                  : ""
              }

              <div class="small text-danger mt-2">
               ${M.requestedReason(
                 escapeHtml(item.requested_quantity),
                 escapeHtml(M.getReorderItemReason(item)),
               )}
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderQuantityAdjustmentsSection(items) {
  if (!items || !items.length) {
    return "";
  }

  return `
    <div class="mb-4">
      <h6 class="mb-3">${M.quantityUpdatesSectionTitle}</h6>
      ${items
        .map(
          (item) => `
            <div class="border border-warning rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>
              <div class="small text-muted mt-2">
                ${M.requestedAdded(escapeHtml(item.requested_quantity), escapeHtml(item.added_quantity))}
              </div>

              ${
                item.reason || item.reason_code
                  ? `
      <div class="small text-warning-emphasis mt-1">
        ${escapeHtml(M.getReorderItemReason(item))}
      </div>
    `
                  : ""
              }
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}
function getPriceUpdateMessage(item) {
  if (item?.message) {
    return item.message;
  }

  const productName = item?.product_name || M.productFallback || "this item";
  const originalPrice = formatMoney(item?.original_price);
  const currentPrice = formatMoney(item?.current_price);

  let message = `Unit price updated for ${productName}: ${originalPrice} → ${currentPrice}.`;

  if (item?.producer_changed) {
    const currentProducer =
      item.current_producer_name || "a different producer";
    const originalProducer = item.original_producer_name || "";

    message += ` This is because the selected replacement is supplied by ${currentProducer}`;

    if (originalProducer) {
      message += ` instead of ${originalProducer}`;
    }

    message += ".";
  } else if (item?.pricing_source === "surplus") {
    message += " This is because surplus pricing is currently applied.";
  } else if (item?.pricing_source === "wholesale") {
    message += " This is because wholesale pricing is currently applied.";
  } else {
    message +=
      " This is because the current unit price is different from the previous order.";
  }

  return message;
}
function renderPriceChangesSection(items) {
  if (!items || !items.length) {
    return "";
  }

  return `
    <div class="mb-0">
      <h6 class="mb-3">${M.priceUpdatesSectionTitle}</h6>
      ${items
        .map(
          (item) => `
            <div class="border border-primary rounded p-3 mb-2 bg-light">
              <div class="fw-semibold">${escapeHtml(item.product_name)}</div>

              ${
                item.current_producer_name || item.producer_name
                  ? `
                    <div class="small text-muted mt-1">
                      ${M.producerLine(
                        escapeHtml(
                          item.current_producer_name || item.producer_name,
                        ),
                      )}
                    </div>
                  `
                  : ""
              }

              <div class="small text-primary mt-2">
                ${escapeHtml(getPriceUpdateMessage(item))}
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderReorderResult(result) {
  const counts = getResultCounts(result);
  const hasUpdates =
    counts.unavailable > 0 ||
    counts.quantityAdjusted > 0 ||
    counts.priceChanged > 0;

  const title = counts.added > 0 ? M.selectedAddedBody : M.noItemsAddedBody;

  const body = hasUpdates ? M.resultUpdatesBody : M.resultSuccessBody;

  return `
    <div class="border rounded p-3 mb-4 bg-light">
      <div class="fw-semibold mb-1">${escapeHtml(title)}</div>
      <div class="small text-muted">
        ${escapeHtml(body)}
      </div>
      ${renderResultSummaryBadges(result)}
    </div>

    ${renderAddedItemsSection(result.added_items || [])}
    ${renderUnavailableItemsSection(result.unavailable_items || [])}
    ${renderQuantityAdjustmentsSection(result.quantity_adjusted_items || [])}
    ${renderPriceChangesSection(result.price_changed_items || [])}
  `;
}

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
      throw await buildApiErrorFromResponse(response, M.previewFailed);
    }

    const preview = await response.json();
    reorderPlannerState = buildReorderPlannerState(orderId, preview);
    updateReorderPlannerUI();
  } catch (error) {
    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");
    const title = document.getElementById("reorderModalTitle");

    reorderPlannerState = null;

    if (title) title.textContent = M.previewTitle;
    if (content) {
      content.innerHTML = `
        <div class="alert alert-danger mb-0">
          ${escapeHtml(M.getPreviewError(error))}
        </div>
      `;
    }

    if (footer) {
      footer.innerHTML = `
        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
          ${M.closeButton}
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
      throw await buildApiErrorFromResponse(response, M.reorderFailed);
    }

    const result = await response.json();
    showReorderResultToasts(result);

    const content = document.getElementById("reorderModalContent");
    const footer = document.getElementById("reorderModalFooter");
    const title = document.getElementById("reorderModalTitle");

    reorderPlannerState = null;

    if (title) title.textContent = M.successTitle;
    if (content) content.innerHTML = renderReorderResult(result);
    if (footer) footer.innerHTML = REORDER_RESULT_FOOTER;

    document.dispatchEvent(
      new CustomEvent("cart:updated", { detail: { action: "reorder" } }),
    );

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
            ${escapeHtml(M.getReorderError(error))}
          </div>
        `,
      );
    }

    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = M.confirmButton;
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
window.OrderHistoryPage = {
  loadOrders,
  openOrderDetails,
};
