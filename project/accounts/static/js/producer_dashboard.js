let selectedSummaryId = null;
let pendingStatusValue = null;
let pendingStatusLabel = null;

let pendingCancelItemId = null;
let pendingCancelProductName = null;
let pendingCancelSummaryId = null;
let pendingCancelActiveQuantity = 0;
let pendingCancelQuantity = 0;
let pendingCancelReason = "";
let pendingReloadSummaryId = null;

// Pagination variables
let currentPage = 1;
let subCurrentPage = 1;
const rowsPerPage = 10;

const STATUS_CONFIRMATION_HELP = {
  PRE: "Use this when work has started on this producer's items.",
  PAC: "Use this only when all items in this producer section have been packed.",
  RFC: "Use this only when a collection order is packed and ready for the customer to collect.",
  SHP: "Use this only when a delivery order has left the producer for delivery.",
  COM: "Use this only when the producer section has been fully fulfilled.",
};

const PRODUCER_STATUS_MAP = {
  PEN: { text: "Pending", cls: "status-pending" },
  PRE: { text: "Preparing", cls: "status-preparing" },
  PAC: { text: "Packaged", cls: "status-packaged" },
  RFC: { text: "Ready for collection", cls: "status-ready" },
  SHP: { text: "Shipped", cls: "status-shipped" },
  COM: { text: "Completed", cls: "status-completed" },
  CAN: { text: "Cancelled", cls: "status-cancelled" },
};

const MESSAGE_VARIANT_CLASSES = {
  success: "alert-success",
  danger: "alert-danger",
  warning: "alert-warning",
  info: "alert-info",
  primary: "alert-primary",
};

/* ============================================================
   Small DOM helpers
============================================================ */

function getProducerStatusInfo(status, fallbackText = null) {
  return (
    PRODUCER_STATUS_MAP[status] || {
      text: fallbackText || status,
      cls: "status-pending",
    }
  );
}

function setElementText(id, value) {
  const element = document.getElementById(id);

  if (element) {
    element.textContent = value ?? "";
  }
}

function getCsrfToken() {
  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  return csrfInput ? csrfInput.value : null;
}

function addListenerIfExists(id, eventName, handler) {
  const element = document.getElementById(id);

  if (element) {
    element.addEventListener(eventName, handler);
  }
}

function setButtonLoading(button, isLoading, loadingText, normalText) {
  if (!button) return;

  button.disabled = isLoading;
  button.textContent = isLoading ? loadingText : normalText;
}

function replaceButton(id) {
  const oldButton = document.getElementById(id);

  if (!oldButton) {
    return null;
  }

  const newButton = oldButton.cloneNode(true);
  oldButton.replaceWith(newButton);
  return newButton;
}

function ensureModalElement(id, html) {
  let modalElement = document.getElementById(id);

  if (!modalElement) {
    document.body.insertAdjacentHTML("beforeend", html);
    modalElement = document.getElementById(id);
  }

  return modalElement;
}

function getModalInstance(modalElement, options = {}) {
  if (!modalElement || !window.bootstrap) {
    return null;
  }

  return bootstrap.Modal.getOrCreateInstance(modalElement, options);
}

function renderDetailLines(container, details = []) {
  if (!container) return;

  container.innerHTML = "";

  details.filter(Boolean).forEach((detail) => {
    const row = document.createElement("p");
    row.className = "mb-2";

    if (typeof detail === "string") {
      row.textContent = detail;
    } else {
      const label = document.createElement("strong");
      label.textContent = `${detail.label}: `;

      const value = document.createElement("span");
      value.textContent = detail.value ?? "";

      row.appendChild(label);
      row.appendChild(value);
    }

    container.appendChild(row);
  });
}
function normaliseOrderSearchValue(value) {
  return String(value || "")
    .trim()
    .replace(/^#+/, "")
    .toLowerCase()
    .replace(/\s+/g, "");
}

function getRowOrderSearchText(row) {
  return [
    row.getAttribute("data-order-id") || "",
    row.getAttribute("data-order-reference") || "",
    row.getAttribute("data-order-db-id") || "",
    row.cells?.[0]?.innerText || "",
  ]
    .join(" ")
    .toLowerCase()
    .replace(/^#+/, "")
    .replace(/\s+/g, "");
}

/* ============================================================
   Reusable professional modals
============================================================ */

function showMessageModal({
  title = "Message",
  message = "",
  details = [],
  variant = "info",
  buttonText = "OK",
} = {}) {
  const modalElement = ensureModalElement(
    "producerMessageModal",
    `
    <div class="modal fade"
         id="producerMessageModal"
         tabindex="-1"
         aria-labelledby="producerMessageModalLabel"
         aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold" id="producerMessageModalLabel">Message</h5>
            <button type="button"
                    class="btn-close"
                    data-bs-dismiss="modal"
                    aria-label="Close"></button>
          </div>

          <div class="modal-body">
            <div id="producerMessageModalAlert" class="alert mb-3"></div>
            <div id="producerMessageModalDetails"></div>
          </div>

          <div class="modal-footer">
            <button type="button"
                    class="btn btn-primary fw-bold"
                    id="producerMessageModalOkBtn">
              OK
            </button>
          </div>
        </div>
      </div>
    </div>
    `,
  );

  const modal = getModalInstance(modalElement);

  if (!modal) {
    console.error(title, message, details);
    return Promise.resolve();
  }

  const titleElement = document.getElementById("producerMessageModalLabel");
  const alertElement = document.getElementById("producerMessageModalAlert");
  const detailsElement = document.getElementById("producerMessageModalDetails");
  const okButton = replaceButton("producerMessageModalOkBtn");

  if (titleElement) titleElement.textContent = title;

  if (alertElement) {
    alertElement.className = `alert mb-3 ${
      MESSAGE_VARIANT_CLASSES[variant] || MESSAGE_VARIANT_CLASSES.info
    }`;
    alertElement.textContent = message;
  }

  renderDetailLines(detailsElement, details);

  if (okButton) {
    okButton.textContent = buttonText;
  }

  return new Promise((resolve) => {
    const closeModal = () => {
      modal.hide();
    };

    if (okButton) {
      okButton.addEventListener("click", closeModal, { once: true });
    }

    modalElement.addEventListener(
      "hidden.bs.modal",
      () => {
        resolve();
      },
      { once: true },
    );

    modal.show();
  });
}

function showConfirmModal({
  title = "Please confirm",
  message = "",
  details = [],
  variant = "warning",
  confirmText = "Confirm",
  cancelText = "Go back",
  confirmButtonClass = "btn-danger",
} = {}) {
  const modalElement = ensureModalElement(
    "producerConfirmModal",
    `
    <div class="modal fade"
         id="producerConfirmModal"
         tabindex="-1"
         aria-labelledby="producerConfirmModalLabel"
         aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold" id="producerConfirmModalLabel">Please confirm</h5>
            <button type="button"
                    class="btn-close"
                    data-bs-dismiss="modal"
                    aria-label="Close"></button>
          </div>

          <div class="modal-body">
            <div id="producerConfirmModalAlert" class="alert mb-3"></div>
            <div id="producerConfirmModalDetails"></div>
          </div>

          <div class="modal-footer">
            <button type="button"
                    class="btn btn-outline-secondary"
                    id="producerConfirmCancelBtn">
              Go back
            </button>
            <button type="button"
                    class="btn btn-danger fw-bold"
                    id="producerConfirmActionBtn">
              Confirm
            </button>
          </div>
        </div>
      </div>
    </div>
    `,
  );

  const modal = getModalInstance(modalElement);

  if (!modal) {
    console.error(title, message, details);
    return Promise.resolve(false);
  }

  const titleElement = document.getElementById("producerConfirmModalLabel");
  const alertElement = document.getElementById("producerConfirmModalAlert");
  const detailsElement = document.getElementById("producerConfirmModalDetails");
  const cancelButton = replaceButton("producerConfirmCancelBtn");
  const confirmButton = replaceButton("producerConfirmActionBtn");

  if (titleElement) titleElement.textContent = title;

  if (alertElement) {
    alertElement.className = `alert mb-3 ${
      MESSAGE_VARIANT_CLASSES[variant] || MESSAGE_VARIANT_CLASSES.warning
    }`;
    alertElement.textContent = message;
  }

  renderDetailLines(detailsElement, details);

  if (cancelButton) {
    cancelButton.textContent = cancelText;
  }

  if (confirmButton) {
    confirmButton.textContent = confirmText;
    confirmButton.className = `btn ${confirmButtonClass} fw-bold`;
  }

  return new Promise((resolve) => {
    let confirmed = false;

    if (cancelButton) {
      cancelButton.addEventListener(
        "click",
        () => {
          modal.hide();
        },
        { once: true },
      );
    }

    if (confirmButton) {
      confirmButton.addEventListener(
        "click",
        () => {
          confirmed = true;
          modal.hide();
        },
        { once: true },
      );
    }

    modalElement.addEventListener(
      "hidden.bs.modal",
      () => {
        resolve(confirmed);
      },
      { once: true },
    );

    modal.show();
  });
}

function showTextInputModal({
  title = "Enter details",
  message = "",
  label = "Reason",
  placeholder = "",
  initialValue = "",
  required = true,
  confirmText = "Continue",
  cancelText = "Go back",
} = {}) {
  const modalElement = ensureModalElement(
    "producerTextInputModal",
    `
    <div class="modal fade"
         id="producerTextInputModal"
         tabindex="-1"
         aria-labelledby="producerTextInputModalLabel"
         aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold" id="producerTextInputModalLabel">Enter details</h5>
            <button type="button"
                    class="btn-close"
                    data-bs-dismiss="modal"
                    aria-label="Close"></button>
          </div>

          <div class="modal-body">
            <div class="alert alert-warning mb-3" id="producerTextInputModalMessage"></div>

            <label for="producerTextInputField" class="form-label fw-bold" id="producerTextInputLabel">
              Reason
            </label>
            <textarea class="form-control"
                      id="producerTextInputField"
                      rows="4"></textarea>

            <div id="producerTextInputError"
                 class="alert alert-danger py-2 mt-3 d-none"></div>
          </div>

          <div class="modal-footer">
            <button type="button"
                    class="btn btn-outline-secondary"
                    id="producerTextInputCancelBtn">
              Go back
            </button>
            <button type="button"
                    class="btn btn-primary fw-bold"
                    id="producerTextInputConfirmBtn">
              Continue
            </button>
          </div>
        </div>
      </div>
    </div>
    `,
  );

  const modal = getModalInstance(modalElement);

  if (!modal) {
    console.error(title, message);
    return Promise.resolve(null);
  }

  const titleElement = document.getElementById("producerTextInputModalLabel");
  const messageElement = document.getElementById(
    "producerTextInputModalMessage",
  );
  const labelElement = document.getElementById("producerTextInputLabel");
  const inputElement = document.getElementById("producerTextInputField");
  const errorElement = document.getElementById("producerTextInputError");
  const cancelButton = replaceButton("producerTextInputCancelBtn");
  const confirmButton = replaceButton("producerTextInputConfirmBtn");

  if (titleElement) titleElement.textContent = title;
  if (messageElement) messageElement.textContent = message;
  if (labelElement) labelElement.textContent = label;

  if (inputElement) {
    inputElement.value = initialValue;
    inputElement.placeholder = placeholder;
  }

  if (errorElement) {
    errorElement.classList.add("d-none");
    errorElement.textContent = "";
  }

  if (cancelButton) cancelButton.textContent = cancelText;
  if (confirmButton) confirmButton.textContent = confirmText;

  return new Promise((resolve) => {
    let submittedValue = null;
    let submitted = false;

    if (cancelButton) {
      cancelButton.addEventListener(
        "click",
        () => {
          modal.hide();
        },
        { once: true },
      );
    }

    if (confirmButton) {
      confirmButton.addEventListener("click", () => {
        const value = (inputElement?.value || "").trim();

        if (required && !value) {
          if (errorElement) {
            errorElement.textContent =
              "A reason is required before this action can continue.";
            errorElement.classList.remove("d-none");
          }
          return;
        }

        submitted = true;
        submittedValue = value;
        modal.hide();
      });
    }

    modalElement.addEventListener(
      "shown.bs.modal",
      () => {
        inputElement?.focus();
      },
      { once: true },
    );

    modalElement.addEventListener(
      "hidden.bs.modal",
      () => {
        resolve(submitted ? submittedValue : null);
      },
      { once: true },
    );

    modal.show();
  });
}

/* ============================================================
   Producer-friendly payment and refund wording
============================================================ */

function getRefundTextBlob(refund) {
  if (!refund) return "";

  return [
    refund.payment_method,
    refund.payment_type,
    refund.payment_provider,
    refund.payment_status,
    refund.refund_status,
    refund.status,
    refund.message,
    refund.reason,
    refund.error,
    refund.detail,
  ]
    .filter((value) => value !== undefined && value !== null)
    .map((value) => String(value).toLowerCase())
    .join(" ");
}

function isCashRefundContext(refund) {
  const text = getRefundTextBlob(refund);

  return (
    refund?.is_cash_order === true ||
    refund?.cash_order === true ||
    refund?.payment_method === "CASH" ||
    refund?.payment_method === "cash" ||
    refund?.payment_type === "CASH" ||
    refund?.payment_type === "cash" ||
    text.includes("cash order") ||
    text.includes("cash payment") ||
    text.includes("not paid online") ||
    text.includes("no online payment") ||
    text.includes("offline payment")
  );
}

function isCardRefundContext(refund) {
  const text = getRefundTextBlob(refund);

  return (
    refund?.is_card_order === true ||
    refund?.card_order === true ||
    refund?.payment_method === "CARD" ||
    refund?.payment_method === "card" ||
    refund?.payment_type === "CARD" ||
    refund?.payment_type === "card" ||
    text.includes("card order") ||
    text.includes("card payment") ||
    text.includes("stripe") ||
    text.includes("payment provider") ||
    text.includes("online payment") ||
    text.includes("payment intent")
  );
}

function isDemoRefundContext(refund) {
  const text = getRefundTextBlob(refund);

  return (
    refund?.simulated === true ||
    refund?.demo === true ||
    refund?.demo_mode === true ||
    text.includes("demo") ||
    text.includes("simulated") ||
    text.includes("locally")
  );
}

function isAlreadyRefundedContext(refund) {
  const text = getRefundTextBlob(refund);

  return (
    refund?.already_refunded === true ||
    refund?.already_processed === true ||
    text.includes("already processed") ||
    text.includes("already refunded") ||
    text.includes("fully refunded")
  );
}

function isNoSuccessfulCardPaymentContext(refund) {
  const text = getRefundTextBlob(refund);

  return (
    refund?.no_successful_payment === true ||
    refund?.no_successful_card_payment === true ||
    text.includes("no successful card payment") ||
    text.includes("no successful payment") ||
    text.includes("payment was not successful") ||
    text.includes("payment failed")
  );
}

function isRefundedContext(refund) {
  return (
    refund?.refunded === true ||
    refund?.refund_created === true ||
    refund?.refund_requested === true ||
    refund?.status === "refunded" ||
    refund?.status === "success" ||
    refund?.refund_status === "refunded" ||
    refund?.refund_status === "success"
  );
}

function getPaymentContextLabel(refund) {
  if (isCashRefundContext(refund)) {
    return "Cash order";
  }

  if (isCardRefundContext(refund)) {
    return "Card order";
  }

  return "Payment update";
}

function formatRefundMessage(refund) {
  if (!refund) {
    return "The cancellation was recorded, but payment adjustment details were not returned by the system.";
  }

  const rawMessage = String(refund.message || refund.reason || "").trim();

  if (isCashRefundContext(refund)) {
    return "No card refund was needed because this was a cash order.";
  }

  if (isAlreadyRefundedContext(refund)) {
    return "The customer refund had already been processed.";
  }

  if (isNoSuccessfulCardPaymentContext(refund)) {
    return "No successful card payment was found, so no automatic card refund was made.";
  }

  if (isRefundedContext(refund)) {
    return "The customer will receive the refund soon.";
  }

  if (isCardRefundContext(refund)) {
    return "The cancellation was recorded. Check the payment record if a card refund is still expected.";
  }

  if (rawMessage) {
    return rawMessage;
  }

  return "The cancellation was recorded. No automatic card refund update was returned.";
}

function getCancellationCompletionMessage(refund, context = "item") {
  const itemText =
    context === "producer_order"
      ? "This producer section has been cancelled."
      : "The item quantity has been cancelled.";

  if (isCashRefundContext(refund)) {
    return `${itemText} No card refund was needed because this was a cash order.`;
  }

  if (isRefundedContext(refund) || isAlreadyRefundedContext(refund)) {
    return `${itemText} The customer will receive the refund soon.`;
  }

  if (isNoSuccessfulCardPaymentContext(refund)) {
    return `${itemText} No successful card payment was found, so no automatic card refund was made.`;
  }

  return `${itemText} The cancellation has been recorded.`;
}

function getRefundAmountLabel(refund) {
  if (isCashRefundContext(refund)) {
    return "Cancelled cash amount";
  }

  if (isCardRefundContext(refund) || isRefundedContext(refund)) {
    return "Refund amount";
  }

  return "Payment adjustment amount";
}

function getRefundAmountText(refund) {
  if (!refund || refund.amount === undefined || refund.amount === null) {
    return null;
  }

  const numericAmount = Number(refund.amount);

  if (Number.isNaN(numericAmount)) {
    return String(refund.amount);
  }

  return `£${numericAmount.toFixed(2)}`;
}

function getRefundDetails(refund) {
  const refundAmountText = getRefundAmountText(refund);

  return [
    { label: "Payment type", value: getPaymentContextLabel(refund) },
    refundAmountText
      ? { label: getRefundAmountLabel(refund), value: refundAmountText }
      : null,
    { label: "Payment update", value: formatRefundMessage(refund) },
  ];
}

/* ============================================================
   Status filtering and pagination
============================================================ */

function parseAllowedStatuses(rowElement) {
  if (!rowElement) return [];

  try {
    return JSON.parse(rowElement.getAttribute("data-allowed-statuses") || "[]");
  } catch (error) {
    console.error("Invalid allowed status JSON:", error);
    return [];
  }
}

function createStatusActionButton(status, options = {}) {
  const button = document.createElement("button");
  const actionLabel = getStatusActionText(status.value, status.label);

  button.type = "button";
  button.className = options.className || "btn btn-primary fw-bold";
  button.textContent = actionLabel;
  button.addEventListener("click", () => {
    openStatusConfirmModal(status.value, status.label);
  });

  return button;
}

function renderTopStatusActionMenu(allowedStatuses) {
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

  menu.innerHTML = "";

  allowedStatuses.forEach((status) => {
    const item = document.createElement("li");
    const button = createStatusActionButton(status, {
      className: "dropdown-item fw-bold",
    });

    item.appendChild(button);
    menu.appendChild(item);
  });

  updateBtn.disabled = false;
}

function renderDetailStatusActionArea(allowedStatuses) {
  const area = document.querySelector(
    "#detailsContent .detail-status-action-area",
  );

  if (!area) return;

  area.innerHTML = "";

  if (!allowedStatuses || allowedStatuses.length === 0) {
    const message = document.createElement("div");
    message.className = "producer-next-action-complete";
    message.innerHTML = `
      <strong>No further status update is available.</strong>
      <div class="small mt-1">
        This producer section is already complete, shipped, cancelled, or has no valid next stage.
      </div>
    `;
    area.appendChild(message);
    return;
  }

  if (allowedStatuses.length === 1) {
    const status = allowedStatuses[0];
    const helpText =
      STATUS_CONFIRMATION_HELP[status.value] ||
      "Only continue if this status is correct.";

    const wrapper = document.createElement("div");
    wrapper.className = "detail-status-single-action";

    const help = document.createElement("p");
    help.className = "small text-muted mb-2";
    help.textContent = helpText;

    const button = createStatusActionButton(status, {
      className: "btn btn-primary fw-bold detail-status-action-button",
    });

    wrapper.appendChild(help);
    wrapper.appendChild(button);
    area.appendChild(wrapper);
    return;
  }

  const intro = document.createElement("p");
  intro.className = "small text-muted mb-2";
  intro.textContent =
    "Choose the correct next step only after checking this producer section.";

  const grid = document.createElement("div");
  grid.className = "detail-status-action-grid";

  allowedStatuses.forEach((status) => {
    const actionCard = document.createElement("div");
    actionCard.className = "detail-status-action-card";

    const button = createStatusActionButton(status, {
      className: "btn btn-outline-primary fw-bold detail-status-action-button",
    });

    const help = document.createElement("div");
    help.className = "small text-muted mt-2";
    help.textContent =
      STATUS_CONFIRMATION_HELP[status.value] ||
      "Only continue if this status is correct.";

    actionCard.appendChild(button);
    actionCard.appendChild(help);
    grid.appendChild(actionCard);
  });

  area.appendChild(intro);
  area.appendChild(grid);
}

function renderStatusActionMenu(allowedStatuses) {
  renderTopStatusActionMenu(allowedStatuses);
  renderDetailStatusActionArea(allowedStatuses);
}
function applyAllFilters(resetPage = true, resetDetails = true) {
  if (resetPage) {
    currentPage = 1;
  }

  const orderIdSearch = normaliseOrderSearchValue(
    document.getElementById("filterOrderId")?.value,
  );

  const nameSearch = (
    document.getElementById("filterCustomerName")?.value || ""
  )
    .trim()
    .toLowerCase();

  const fromDate = document.getElementById("filterDateFrom")?.value || "";
  const toDate = document.getElementById("filterDateTo")?.value || "";

  const checkedStatuses = Array.from(
    document.querySelectorAll(".status-filter:checked"),
  ).map((checkbox) => checkbox.value);

  const matchingRows = [];

  document.querySelectorAll(".order-row").forEach((row) => {
    const status = row.getAttribute("data-status");
    const orderId = getRowOrderSearchText(row);
    const customerName = (row.getAttribute("data-customer-name") || "").toLowerCase();
    const dueDate = row.getAttribute("data-due-date") || "";

    const orderIdMatch = !orderIdSearch || orderId.includes(orderIdSearch);
    const nameMatch = !nameSearch || customerName.includes(nameSearch);
    const fromMatch = fromDate === "" || dueDate >= fromDate;
    const toMatch = toDate === "" || dueDate <= toDate;

    /*
      Important:
      If an order reference is typed, search across every status.
      This prevents cancelled/completed orders being hidden just because their
      status checkbox is not ticked by default.
    */
    const statusMatch =
      Boolean(orderIdSearch) || checkedStatuses.includes(status);

    if (statusMatch && orderIdMatch && nameMatch && fromMatch && toMatch) {
      matchingRows.push(row);
    } else {
      row.style.display = "none";
    }
  });

  const totalRows = matchingRows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

  if (currentPage > totalPages) {
    currentPage = totalPages;
  }

  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;

  matchingRows.forEach((row, index) => {
    row.style.display = index >= startIndex && index < endIndex ? "" : "none";
  });

  const emptyRow = document.getElementById("emptyStateRow");

  if (emptyRow) {
    emptyRow.style.display = totalRows === 0 ? "" : "none";
  }

  renderPagination(totalPages);

  if (resetDetails) {
    selectedSummaryId = null;

    document
      .querySelectorAll(".order-row")
      .forEach((row) => row.classList.remove("selected"));

    document
      .querySelectorAll(".sub-row")
      .forEach((row) => row.classList.remove("selected"));

    setElementText("detailOrderId", "Select an order");

    const detailsContent = document.getElementById("detailsContent");

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
            <li>Use <strong>Filter</strong> to find orders by status, order reference, customer name, or due date.</li>
            <li>Searching by order reference checks all statuses, including completed and cancelled orders.</li>
            <li>Click one order row to open its full details.</li>
            <li>Use the <strong>Next action</strong> button inside Further Details only when the producer section has really moved to the next stage.</li>
            <li>A confirmation box will appear before the status is saved.</li>
            <li>Status cannot be moved backwards. If a mistake is made, contact an admin.</li>
          </ol>
        </div>
      `;
    }

    const updateBtn = document.getElementById("updateStatusBtn");

    if (updateBtn) {
      updateBtn.disabled = true;
    }

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

function renderPagination(totalPages) {
  const container = document.getElementById("paginationContainer");

  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = '<ul class="pagination mb-0 shadow-sm">';

  html += `
    <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
      <button class="page-link"
              onclick="goToPage(${currentPage - 1})"
              style="color: var(--brand);">
        Previous
      </button>
    </li>
  `;

  for (let page = 1; page <= totalPages; page += 1) {
    const activeClass = currentPage === page ? "active" : "";
    const activeStyle =
      currentPage === page
        ? "background-color: #3a4b53; border-color: #3a4b53; color: #fff;"
        : "color: var(--brand);";

    html += `
      <li class="page-item ${activeClass}">
        <button class="page-link"
                onclick="goToPage(${page})"
                style="${activeStyle}">
          ${page}
        </button>
      </li>
    `;
  }

  html += `
    <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
      <button class="page-link"
              onclick="goToPage(${currentPage + 1})"
              style="color: var(--brand);">
        Next
      </button>
    </li>
  `;

  html += "</ul>";
  container.innerHTML = html;
}

function goToPage(pageNumber) {
  currentPage = pageNumber;
  applyAllFilters(false);
}

function clearFilters() {
  const filterOrderId = document.getElementById("filterOrderId");
  const filterCustomerName = document.getElementById("filterCustomerName");
  const filterDateFrom = document.getElementById("filterDateFrom");
  const filterDateTo = document.getElementById("filterDateTo");

  if (filterOrderId) filterOrderId.value = "";
  if (filterCustomerName) filterCustomerName.value = "";
  if (filterDateFrom) filterDateFrom.value = "";
  if (filterDateTo) filterDateTo.value = "";

  const defaults = {
    filterPen: true,
    filterPre: true,
    filterPac: true,
    filterRfc: true,
    filterShp: true,
    filterCom: false,
    filterCan: false,
  };

  Object.entries(defaults).forEach(([id, checked]) => {
    const input = document.getElementById(id);

    if (input) {
      input.checked = checked;
    }
  });

  applyAllFilters(true);
}

/* ============================================================
   Details panel
============================================================ */

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
  setElementText("detailOrderId", `Order ${orderRef}`);

  const template = document.getElementById(`details-template-${summaryId}`);
  const detailsContent = document.getElementById("detailsContent");

  if (template && detailsContent) {
    detailsContent.innerHTML = template.innerHTML;
  }

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

  if (!filterId) return;

  const input = document.getElementById(filterId);

  if (input) {
    input.checked = true;
  }
}

function getCurrentOrderFilterValues() {
  return {
    orderIdSearch: normaliseOrderSearchValue(
      document.getElementById("filterOrderId")?.value,
    ),
    nameSearch: (
      document.getElementById("filterCustomerName")?.value || ""
    )
      .trim()
      .toLowerCase(),
    fromDate: document.getElementById("filterDateFrom")?.value || "",
    toDate: document.getElementById("filterDateTo")?.value || "",
    checkedStatuses: Array.from(
      document.querySelectorAll(".status-filter:checked"),
    ).map((checkbox) => checkbox.value),
  };
}

function rowMatchesCurrentOrderFilters(row) {
  const filters = getCurrentOrderFilterValues();

  const status = row.getAttribute("data-status");
  const orderId = getRowOrderSearchText(row);
  const customerName = (row.getAttribute("data-customer-name") || "").toLowerCase();
  const dueDate = row.getAttribute("data-due-date") || "";

  const statusMatch =
    Boolean(filters.orderIdSearch) || filters.checkedStatuses.includes(status);

  if (!statusMatch) return false;
  if (filters.orderIdSearch && !orderId.includes(filters.orderIdSearch)) return false;
  if (filters.nameSearch && !customerName.includes(filters.nameSearch)) return false;
  if (filters.fromDate !== "" && dueDate < filters.fromDate) return false;
  if (filters.toDate !== "" && dueDate > filters.toDate) return false;

  return true;
}

function getMatchingOrderRowsForCurrentFilters() {
  return Array.from(document.querySelectorAll(".order-row")).filter(
    rowMatchesCurrentOrderFilters,
  );
}

function moveToPageContainingSummary(summaryId) {
  const row = document.getElementById(`row-${summaryId}`);

  if (!row) return false;

  const matchingRows = getMatchingOrderRowsForCurrentFilters();
  const rowIndex = matchingRows.indexOf(row);

  if (rowIndex === -1) return false;

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
  if (!summaryId) return false;

  const row = document.getElementById(`row-${summaryId}`);

  if (!row) return false;

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

  // Forces a fresh page request even when the same order is already open.
  url.searchParams.set("_producer_refresh", String(Date.now()));

  url.hash = "producerDetailsCard";

  window.location.replace(url.toString());
}

function showSubscriptionDetails(subId, rowElement) {
  selectedSummaryId = null;

  document
    .querySelectorAll(".order-row")
    .forEach((row) => row.classList.remove("selected"));

  document
    .querySelectorAll(".sub-row")
    .forEach((row) => row.classList.remove("selected"));

  rowElement.classList.add("selected");

  setElementText("detailOrderId", `Subscription #SUB-${subId}`);

  const template = document.getElementById(`sub-details-template-${subId}`);
  const detailsContent = document.getElementById("detailsContent");

  if (template && detailsContent) {
    detailsContent.innerHTML = template.innerHTML;
  }

  renderStatusActionMenu([]);
}

/* ============================================================
   Producer status update
============================================================ */

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

  setElementText("confirmStatusName", statusLabel);
  setElementText(
    "confirmStatusHelp",
    STATUS_CONFIRMATION_HELP[statusValue] ||
      "Only continue if this status is correct.",
  );

  const modalElement = document.getElementById("statusConfirmModal");
  const modal = getModalInstance(modalElement);

  if (modal) {
    modal.show();
  }
}

function closeStatusConfirmModal() {
  const modalElement = document.getElementById("statusConfirmModal");
  const modal = getModalInstance(modalElement);

  if (modal) {
    modal.hide();
  }
}

async function changeStatus(newStatus) {
  if (!selectedSummaryId) {
    await showMessageModal({
      title: "No order selected",
      message: "Select an order before changing its status.",
      variant: "warning",
    });
    return;
  }

  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    await showMessageModal({
      title: "Security check failed",
      message:
        "The page security token was not found. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  try {
    const response = await fetch(
      `/accounts/update-order-status/${selectedSummaryId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: newStatus }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      await showMessageModal({
        title: "Status could not be updated",
        message: data.error || "The order status could not be updated.",
        variant: "danger",
      });
      return;
    }

    reloadAndReopenSummary(selectedSummaryId);
  } catch (error) {
    console.error("Error updating status:", error);

    await showMessageModal({
      title: "Network problem",
      message:
        "The status update could not be sent. Check the connection and try again.",
      variant: "danger",
    });
  }
}

/* ============================================================
   Subscriptions
============================================================ */

function applySubFilters(resetPage = true) {
  if (resetPage) {
    subCurrentPage = 1;
  }

  const checkedStatuses = Array.from(
    document.querySelectorAll(".sub-status-filter:checked"),
  ).map((checkbox) => checkbox.value);

  const matchingRows = [];

  document.querySelectorAll(".sub-row").forEach((row) => {
    const status = row.getAttribute("data-sub-status");

    if (checkedStatuses.includes(status)) {
      matchingRows.push(row);
    } else {
      row.style.display = "none";
    }
  });

  const totalRows = matchingRows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

  if (subCurrentPage > totalPages) {
    subCurrentPage = totalPages;
  }

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

  html += `
    <li class="page-item ${subCurrentPage === 1 ? "disabled" : ""}">
      <button class="page-link"
              onclick="goToSubPage(${subCurrentPage - 1})"
              style="color: var(--brand);">
        Previous
      </button>
    </li>
  `;

  for (let page = 1; page <= totalPages; page += 1) {
    const activeClass = subCurrentPage === page ? "active" : "";
    const activeStyle =
      subCurrentPage === page
        ? "background-color: #3a4b53; border-color: #3a4b53; color: #fff;"
        : "color: var(--brand);";

    html += `
      <li class="page-item ${activeClass}">
        <button class="page-link"
                onclick="goToSubPage(${page})"
                style="${activeStyle}">
          ${page}
        </button>
      </li>
    `;
  }

  html += `
    <li class="page-item ${subCurrentPage === totalPages ? "disabled" : ""}">
      <button class="page-link"
              onclick="goToSubPage(${subCurrentPage + 1})"
              style="color: var(--brand);">
        Next
      </button>
    </li>
  `;

  html += "</ul>";
  container.innerHTML = html;
}

function goToSubPage(pageNumber) {
  subCurrentPage = pageNumber;
  applySubFilters(false);
}

function clearSubFilters() {
  const active = document.getElementById("subFilterActive");
  const paused = document.getElementById("subFilterPaused");
  const cancelled = document.getElementById("subFilterCancelled");

  if (active) active.checked = true;
  if (paused) paused.checked = true;
  if (cancelled) cancelled.checked = false;

  applySubFilters(true);
}

async function cancelSubscription(subId) {
  const confirmed = await showConfirmModal({
    title: "Cancel subscription",
    message:
      "This will stop future orders from being generated for this subscription.",
    details: [
      "The nearest existing physical order may still remain active depending on the subscription rules.",
      "Only continue if the customer subscription should be cancelled.",
    ],
    variant: "warning",
    confirmText: "Cancel subscription",
    cancelText: "Go back",
    confirmButtonClass: "btn-danger",
  });

  if (!confirmed) return;

  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    await showMessageModal({
      title: "Security check failed",
      message:
        "The page security token was not found. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  try {
    const response = await fetch(`/accounts/cancel-subscription/${subId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "Content-Type": "application/json",
      },
    });

    let data = {};

    try {
      data = await response.json();
    } catch (_error) {
      data = {};
    }

    if (!response.ok) {
      await showMessageModal({
        title: "Subscription could not be cancelled",
        message:
          data.error ||
          "The subscription could not be cancelled. Please try again.",
        variant: "danger",
      });
      return;
    }

    await showMessageModal({
      title: "Subscription cancelled",
      message:
        "The subscription has been cancelled. Future orders will no longer be generated for this subscription.",
      variant: "success",
      buttonText: "Refresh page",
    });

    window.location.reload();
  } catch (error) {
    console.error("Error cancelling subscription:", error);

    await showMessageModal({
      title: "Network problem",
      message:
        "The subscription cancellation could not be sent. Check the connection and try again.",
      variant: "danger",
    });
  }
}

async function toggleSubscription(subId) {
  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    await showMessageModal({
      title: "Security check failed",
      message:
        "The page security token was not found. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  try {
    const response = await fetch(`/accounts/toggle-subscription/${subId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();

    if (!response.ok) {
      await showMessageModal({
        title: "Subscription could not be updated",
        message:
          data.error ||
          "The subscription status could not be changed. Please try again.",
        variant: "danger",
      });
      return;
    }

    const row = document.getElementById(`sub-row-${subId}`);

    if (row) {
      row.setAttribute("data-sub-status", data.new_status);

      const badge = row.querySelector(".sub-status-badge");

      if (badge) {
        badge.textContent = data.new_status_display;
        badge.className = "status-badge sub-status-badge";

        if (data.new_status === "ACTIVE") {
          badge.classList.add("status-packaged");
        } else if (data.new_status === "PAUSED") {
          badge.classList.add("status-pending");
        } else {
          badge.classList.add("status-cancelled");
        }
      }
    }

    const actionText =
      data.new_status === "ACTIVE"
        ? "resumed"
        : data.new_status === "PAUSED"
          ? "paused"
          : "updated";

    await showMessageModal({
      title: "Subscription updated",
      message: `The subscription has been ${actionText}.`,
      variant: "success",
      buttonText: "Refresh page",
    });

    window.location.reload();
  } catch (error) {
    console.error("Error toggling subscription:", error);

    await showMessageModal({
      title: "Network problem",
      message:
        "The subscription update could not be sent. Check the connection and try again.",
      variant: "danger",
    });
  }
}

/* ============================================================
   Producer order cancellation
============================================================ */

async function cancelProducerOrder(summaryId) {
  const reason = await showTextInputModal({
    title: "Cancel producer order",
    message:
      "Use this only when this producer section cannot be fulfilled. The system will handle any card refund or cash-order adjustment that applies.",
    label: "Reason for cancellation",
    placeholder:
      "Example: unable to fulfil this producer order after stock check.",
    confirmText: "Review cancellation",
  });

  if (reason === null) return;

  const confirmed = await showConfirmModal({
    title: "Final cancellation check",
    message:
      "This will cancel this producer section and update the customer payment record where needed.",
    details: [
      { label: "Reason", value: reason },
      "Only this producer section will be cancelled.",
      "Card orders may need a refund. Cash orders do not need a card refund.",
      "This action cannot be undone by the producer dashboard.",
    ],
    variant: "danger",
    confirmText: "Confirm cancellation",
    cancelText: "Go back",
    confirmButtonClass: "btn-danger",
  });

  if (!confirmed) return;

  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    await showMessageModal({
      title: "Security check failed",
      message:
        "The page security token was not found. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  try {
    const response = await fetch(
      `/accounts/cancel-producer-order/${summaryId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      await showMessageModal({
        title: "Producer order could not be cancelled",
        message:
          data.error ||
          "The producer order could not be cancelled. Please try again.",
        variant: "danger",
      });
      return;
    }

    await showMessageModal({
      title: "Producer order cancelled",
      message: getCancellationCompletionMessage(data.refund, "producer_order"),
      details: [
        ...getRefundDetails(data.refund),
        "The page will refresh and reopen this order.",
      ],
      variant: "success",
      buttonText: "Return to order",
    });

    reloadAndReopenSummary(summaryId);
  } catch (error) {
    console.error("Error cancelling producer order:", error);

    await showMessageModal({
      title: "Network problem",
      message:
        "The producer order cancellation could not be sent. Check the connection and try again.",
      variant: "danger",
    });
  }
}

/* ============================================================
   Item quantity cancellation
============================================================ */

function getCancelQuantityErrorElement() {
  let errorElement = document.getElementById("cancelQuantityError");

  if (!errorElement) {
    const modalBody = document.querySelector(
      "#cancelQuantityModal .modal-body",
    );

    if (modalBody) {
      modalBody.insertAdjacentHTML(
        "beforeend",
        `<div id="cancelQuantityError" class="alert alert-danger py-2 mt-3 d-none"></div>`,
      );

      errorElement = document.getElementById("cancelQuantityError");
    }
  }

  return errorElement;
}

function showCancelQuantityFormError(message) {
  const errorElement = getCancelQuantityErrorElement();

  if (errorElement) {
    errorElement.textContent = message;
    errorElement.classList.remove("d-none");
  }
}

function clearCancelQuantityFormError() {
  const errorElement = getCancelQuantityErrorElement();

  if (errorElement) {
    errorElement.textContent = "";
    errorElement.classList.add("d-none");
  }
}

function openCancelQuantityModal(
  itemId,
  productName,
  summaryId,
  activeQuantity,
  cancelWholeItem = false,
) {
  pendingCancelItemId = itemId;
  pendingCancelProductName = productName;
  pendingCancelSummaryId = summaryId;
  pendingCancelActiveQuantity = Number.parseInt(activeQuantity, 10) || 0;
  pendingCancelQuantity = 0;
  pendingCancelReason = "";

  clearCancelQuantityFormError();

  setElementText("cancelQuantityProductName", productName);
  setElementText("cancelQuantityActiveQty", pendingCancelActiveQuantity);

  const quantityInput = document.getElementById("cancelQuantityInput");
  const reasonInput = document.getElementById("cancelQuantityReason");

  if (quantityInput) {
    quantityInput.value = cancelWholeItem ? pendingCancelActiveQuantity : "";
    quantityInput.max = pendingCancelActiveQuantity;
    quantityInput.readOnly = cancelWholeItem;
  }

  if (reasonInput) {
    reasonInput.value = cancelWholeItem
      ? "This item cannot be fulfilled by the producer."
      : "";
  }

  const modalElement = document.getElementById("cancelQuantityModal");
  const modal = getModalInstance(modalElement);

  if (!modal) {
    showMessageModal({
      title: "Cancellation form unavailable",
      message:
        "The cancellation form was not found on this page. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  modal.show();
}

function openCancelQuantityReviewModal() {
  clearCancelQuantityFormError();

  const quantityInput = document.getElementById("cancelQuantityInput");
  const reasonInput = document.getElementById("cancelQuantityReason");

  const quantityToCancel = Number.parseInt(
    (quantityInput?.value || "").trim(),
    10,
  );

  const reason = (reasonInput?.value || "").trim();

  if (!Number.isInteger(quantityToCancel) || quantityToCancel <= 0) {
    showCancelQuantityFormError(
      "Enter a whole number greater than 0 before continuing.",
    );
    return;
  }

  if (quantityToCancel > pendingCancelActiveQuantity) {
    showCancelQuantityFormError(
      `Only ${pendingCancelActiveQuantity} active item(s) remain. The cancellation quantity cannot be higher than this.`,
    );
    return;
  }

  if (!reason) {
    showCancelQuantityFormError(
      "Enter a clear reason before continuing. Example: 2 items expired after stock check.",
    );
    return;
  }

  pendingCancelQuantity = quantityToCancel;
  pendingCancelReason = reason;

  const remainingQuantity = pendingCancelActiveQuantity - pendingCancelQuantity;

  setElementText("reviewCancelProductName", pendingCancelProductName);
  setElementText("reviewCancelActiveQty", pendingCancelActiveQuantity);
  setElementText("reviewCancelQty", pendingCancelQuantity);
  setElementText("reviewRemainingQty", remainingQuantity);
  setElementText("reviewCancelReason", pendingCancelReason);

  const firstModalElement = document.getElementById("cancelQuantityModal");
  const reviewModalElement = document.getElementById(
    "cancelQuantityReviewModal",
  );

  const firstModal = getModalInstance(firstModalElement);
  const reviewModal = getModalInstance(reviewModalElement);

  if (firstModal) {
    firstModal.hide();
  }

  if (!reviewModal) {
    showMessageModal({
      title: "Review form unavailable",
      message:
        "The final cancellation check could not be opened. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  reviewModal.show();
}

async function confirmCancelQuantity() {
  if (!pendingCancelItemId || !pendingCancelQuantity || !pendingCancelReason) {
    await showMessageModal({
      title: "Cancellation details missing",
      message:
        "The cancellation details are incomplete. Return to the item and try again.",
      variant: "danger",
    });
    return;
  }

  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    await showMessageModal({
      title: "Security check failed",
      message:
        "The page security token was not found. Refresh the page and try again.",
      variant: "danger",
    });
    return;
  }

  const confirmButton = document.getElementById("confirmCancelQuantityBtn");
  setButtonLoading(
    confirmButton,
    true,
    "Cancelling...",
    "Confirm cancellation",
  );

  try {
    const response = await fetch(
      `/accounts/cancel-producer-order-item/${pendingCancelItemId}/`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          reason: pendingCancelReason,
          quantity_to_cancel: pendingCancelQuantity,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      await showMessageModal({
        title: "Item could not be cancelled",
        message:
          data.error ||
          "The item quantity could not be cancelled. Please try again.",
        variant: "danger",
      });
      return;
    }

    const reviewModalElement = document.getElementById(
      "cancelQuantityReviewModal",
    );

    const reviewModal = getModalInstance(reviewModalElement);

    if (reviewModal) {
      reviewModal.hide();
    }

    pendingReloadSummaryId = pendingCancelSummaryId || selectedSummaryId;

    const cancelledQuantity = data.cancelled_quantity || pendingCancelQuantity;
    const remainingQuantity = Math.max(
      pendingCancelActiveQuantity - cancelledQuantity,
      0,
    );

    await showMessageModal({
      title: "Cancellation processed",
      message: getCancellationCompletionMessage(data.refund, "item"),
      details: [
        { label: "Product", value: pendingCancelProductName || "Product" },
        { label: "Cancelled quantity", value: cancelledQuantity },
        { label: "Quantity still to prepare", value: remainingQuantity },
        ...getRefundDetails(data.refund),
        "The page will refresh and reopen this order.",
      ],
      variant: "success",
      buttonText: "Return to order",
    });

    reloadAndReopenSummary(pendingReloadSummaryId || selectedSummaryId);
  } catch (error) {
    console.error("Error cancelling producer order item:", error);

    await showMessageModal({
      title: "Network problem",
      message:
        "The item cancellation could not be sent. Check the connection and try again.",
      variant: "danger",
    });
  } finally {
    setButtonLoading(
      confirmButton,
      false,
      "Cancelling...",
      "Confirm cancellation",
    );
  }
}

/* ============================================================
   Page initialisation
============================================================ */
function normaliseOrderSearchValue(value) {
  return String(value || "")
    .trim()
    .replace(/^#+/, "")
    .toLowerCase()
    .replace(/\s+/g, "");
}

function getRowOrderSearchText(row) {
  return [
    row.getAttribute("data-order-id") || "",
    row.getAttribute("data-order-reference") || "",
    row.getAttribute("data-order-db-id") || "",
  ]
    .join(" ")
    .toLowerCase()
    .replace(/^#+/, "")
    .replace(/\s+/g, "");
}

document.addEventListener("DOMContentLoaded", () => {
  const resetAndFilter = () => applyAllFilters(true);

  addListenerIfExists("filterOrderId", "input", resetAndFilter);
  addListenerIfExists("filterCustomerName", "input", resetAndFilter);
  addListenerIfExists("filterDateFrom", "change", resetAndFilter);
  addListenerIfExists("filterDateTo", "change", resetAndFilter);

  document.querySelectorAll(".status-filter").forEach((checkbox) => {
    checkbox.addEventListener("change", resetAndFilter);
  });

  document.querySelectorAll(".sub-status-filter").forEach((checkbox) => {
    checkbox.addEventListener("change", () => applySubFilters(true));
  });

  const params = new URLSearchParams(window.location.search);
  const openOrderId = params.get("open_order");
  const savedProducerPage = Number(params.get("producer_page"));

  if (Number.isFinite(savedProducerPage) && savedProducerPage > 0) {
    currentPage = savedProducerPage;
  }

  applyAllFilters(false);
  applySubFilters(true);

  const confirmStatusUpdateButton = document.getElementById(
    "confirmStatusUpdateBtn",
  );

  if (confirmStatusUpdateButton) {
    confirmStatusUpdateButton.addEventListener("click", async () => {
      if (!pendingStatusValue) return;

      setButtonLoading(
        confirmStatusUpdateButton,
        true,
        "Updating...",
        "Confirm update",
      );

      await changeStatus(pendingStatusValue);

      setButtonLoading(
        confirmStatusUpdateButton,
        false,
        "Updating...",
        "Confirm update",
      );

      pendingStatusValue = null;
      pendingStatusLabel = null;

      closeStatusConfirmModal();
    });
  }

  const confirmCancelQuantityButton = document.getElementById(
    "confirmCancelQuantityBtn",
  );

  if (confirmCancelQuantityButton) {
    confirmCancelQuantityButton.textContent = "Confirm cancellation";
  }

  addListenerIfExists(
    "reviewCancelQuantityBtn",
    "click",
    openCancelQuantityReviewModal,
  );

  addListenerIfExists(
    "confirmCancelQuantityBtn",
    "click",
    confirmCancelQuantity,
  );

  if (openOrderId) {
    setTimeout(() => {
      openSummaryDetails(openOrderId, true);
    }, 80);
  }
});
