const CUSTOMER_ORDER_CANCEL_API_BASE = "/api/orders/customer/orders/";

document.addEventListener("click", async (event) => {
  const itemCancelBtn = event.target.closest(
    "[data-action='cancel-customer-order-item']",
  );

  if (itemCancelBtn) {
    event.preventDefault();

    if (itemCancelBtn.disabled) {
      return;
    }

    await handleCustomerOrderItemCancellation(itemCancelBtn);
    return;
  }

  const cancelBtn = event.target.closest(
    "[data-action='cancel-customer-order']",
  );

  if (!cancelBtn) {
    return;
  }

  event.preventDefault();

  if (cancelBtn.disabled) {
    return;
  }

  await handleCustomerOrderCancellation(cancelBtn);
});

async function handleCustomerOrderCancellation(button) {
  const orderId = button.dataset.orderId;
  const orderNumber = button.dataset.orderNumber || `#${orderId}`;

  if (!orderId) {
    await showCancellationModal({
      title: "Cancellation unavailable",
      message: "Order ID is missing.",
      variant: "danger",
    });
    return;
  }

  const result = await showCancellationReasonModal({
    title: `Cancel order ${orderNumber}`,
    intro:
      "Please confirm that this order should be cancelled. A reason can be added for the order record.",
    warning:
      "This action will cancel the order and update the order history.",
    reasonLabel: "Cancellation reason",
    reasonPlaceholder: "Optional. Leave blank to use the default reason.",
    confirmText: "Cancel order",
  });

  if (!result.confirmed) {
    return;
  }

  await submitCustomerOrderCancellation(button, orderId, result.reason);
}

async function handleCustomerOrderItemCancellation(button) {
  const orderId = button.dataset.orderId;
  const itemId = button.dataset.itemId;
  const productName = button.dataset.productName || "this item";
  const activeQuantity = Number(button.dataset.activeQuantity || 0);

  if (!orderId || !itemId) {
    await showCancellationModal({
      title: "Cancellation unavailable",
      message: "Order item details are missing.",
      variant: "danger",
    });
    return;
  }

  if (!Number.isFinite(activeQuantity) || activeQuantity <= 0) {
    await showCancellationModal({
      title: "Cancellation unavailable",
      message: "This item has no active quantity left to cancel.",
      variant: "danger",
    });
    return;
  }

  const result = await showCancellationReasonModal({
    title: `Cancel ${productName}`,
    intro:
      "Please confirm that the remaining active quantity for this item should be cancelled.",
    warning:
      "This will cancel the active quantity for this item only. Other active items in the order will stay unchanged.",
    reasonLabel: "Cancellation reason",
    reasonPlaceholder: "Optional. Leave blank to use the default reason.",
    confirmText: "Cancel item",
    details: [
      {
        label: "Item",
        value: productName,
      },
      {
        label: "Active quantity",
        value: `${activeQuantity}`,
      },
    ],
  });

  if (!result.confirmed) {
    return;
  }

  await submitCustomerOrderItemCancellation(button, {
    orderId,
    itemId,
    reason: result.reason,
  });
}

async function submitCustomerOrderCancellation(button, orderId, reason) {
  const originalText = button.textContent;

  setButtonLoading(button, "Cancelling...");

  try {
    const response = await fetch(
      `${CUSTOMER_ORDER_CANCEL_API_BASE}${encodeURIComponent(orderId)}/cancel/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          reason: reason || "",
        }),
      },
    );

    if (!response.ok) {
      throw await buildCancellationApiError(response);
    }

    const payload = await response.json();

    await refreshOrderHistoryState(orderId);

    await showCancellationModal({
      title: "Order cancelled",
      message: buildCancellationSuccessMessage(
        payload,
        "Order cancelled successfully.",
      ),
      variant: "success",
    });
  } catch (error) {
    button.disabled = false;
    button.textContent = originalText;

    await showCancellationModal({
      title: "Order cancellation failed",
      message: error.message || "Order cancellation failed.",
      variant: "danger",
    });
  }
}

async function submitCustomerOrderItemCancellation(
  button,
  { orderId, itemId, reason },
) {
  const originalText = button.textContent;

  setButtonLoading(button, "Cancelling...");

  try {
    const response = await fetch(
      `${CUSTOMER_ORDER_CANCEL_API_BASE}${encodeURIComponent(orderId)}/items/${encodeURIComponent(itemId)}/cancel/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          reason: reason || "",
        }),
      },
    );

    if (!response.ok) {
      throw await buildCancellationApiError(response);
    }

    const payload = await response.json();

    await refreshOrderHistoryState(orderId);

    await showCancellationModal({
      title: "Item cancelled",
      message: buildCancellationSuccessMessage(
        payload,
        "Order item cancelled successfully.",
      ),
      variant: "success",
    });
  } catch (error) {
    button.disabled = false;
    button.textContent = originalText;

    await showCancellationModal({
      title: "Item cancellation failed",
      message: error.message || "Order item cancellation failed.",
      variant: "danger",
    });
  }
}

async function refreshOrderHistoryState(orderId) {
  if (window.OrderHistoryPage?.loadOrders) {
    await window.OrderHistoryPage.loadOrders();
  }

  if (window.OrderHistoryPage?.openOrderDetails) {
    await window.OrderHistoryPage.openOrderDetails(orderId);
  }
}

function setButtonLoading(button, loadingText) {
  button.disabled = true;
  button.textContent = loadingText;
}

function buildCancellationSuccessMessage(payload, fallbackMessage) {
  const refund = payload?.refund;

  if (!refund) {
    return fallbackMessage;
  }

  if (refund.refunded === true) {
    const amountText = formatRefundAmount(refund.amount);

    if (amountText) {
      return `${fallbackMessage} A refund of ${amountText} has been requested to the original payment method. Most card refunds appear within 5–10 business days, depending on the bank.`;
    }

    return `${fallbackMessage} A refund has been requested to the original payment method. Most card refunds appear within 5–10 business days, depending on the bank.`;
  }

  if (refund.reason) {
    return `${fallbackMessage} ${refund.reason}`;
  }

  return fallbackMessage;
}

function formatRefundAmount(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  const amount = Number(value);

  if (!Number.isFinite(amount)) {
    return "";
  }

  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(amount);
}

async function buildCancellationApiError(response) {
  let payload = null;

  try {
    payload = await response.clone().json();
  } catch {
    payload = null;
  }

  const message =
    payload?.error ||
    payload?.detail ||
    payload?.message ||
    `Request failed with status ${response.status}.`;

  const error = new Error(message);
  error.status = response.status;
  error.payload = payload;
  return error;
}

function showCancellationReasonModal({
  title,
  intro,
  warning,
  reasonLabel,
  reasonPlaceholder,
  confirmText,
  details = [],
}) {
  return new Promise((resolve) => {
    const modalElement = createBaseModal({
      title,
      sizeClass: "modal-dialog-centered",
    });

    const body = modalElement.querySelector(".modal-body");
    const footer = modalElement.querySelector(".modal-footer");

    if (intro) {
      const introText = document.createElement("p");
      introText.className = "mb-3";
      introText.textContent = intro;
      body.appendChild(introText);
    }

    if (details.length > 0) {
      const detailList = document.createElement("dl");
      detailList.className = "row small bg-light border rounded-3 p-3 mb-3";

      details.forEach((detail) => {
        const term = document.createElement("dt");
        term.className = "col-sm-4 text-muted";
        term.textContent = detail.label;

        const description = document.createElement("dd");
        description.className = "col-sm-8 mb-2";
        description.textContent = detail.value;

        detailList.appendChild(term);
        detailList.appendChild(description);
      });

      body.appendChild(detailList);
    }

    if (warning) {
      const warningBox = document.createElement("div");
      warningBox.className = "alert alert-warning mb-3";
      warningBox.setAttribute("role", "alert");
      warningBox.textContent = warning;
      body.appendChild(warningBox);
    }

    const reasonWrapper = document.createElement("div");
    reasonWrapper.className = "mb-0";

    const reasonInputId = `cancellationReason-${Date.now()}`;

    const label = document.createElement("label");
    label.className = "form-label fw-semibold";
    label.setAttribute("for", reasonInputId);
    label.textContent = reasonLabel || "Cancellation reason";

    const textarea = document.createElement("textarea");
    textarea.className = "form-control";
    textarea.id = reasonInputId;
    textarea.rows = 4;
    textarea.placeholder =
      reasonPlaceholder || "Optional. Leave blank to use the default reason.";

    const helpText = document.createElement("div");
    helpText.className = "form-text";
    helpText.textContent =
      "This note will be stored with the cancellation record.";

    reasonWrapper.appendChild(label);
    reasonWrapper.appendChild(textarea);
    reasonWrapper.appendChild(helpText);
    body.appendChild(reasonWrapper);

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "btn btn-outline-secondary";
    closeButton.dataset.bsDismiss = "modal";
    closeButton.textContent = "Keep order";

    const confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.className = "btn btn-danger";
    confirmButton.textContent = confirmText || "Confirm cancellation";

    footer.appendChild(closeButton);
    footer.appendChild(confirmButton);

    openBootstrapModal(modalElement, {
      onShown: () => {
        textarea.focus();
      },
      onHiddenWithoutAction: () => {
        resolve({
          confirmed: false,
          reason: "",
        });
      },
    });

    confirmButton.addEventListener("click", () => {
      resolve({
        confirmed: true,
        reason: textarea.value.trim(),
      });

      closeBootstrapModal(modalElement);
    });
  });
}

function showCancellationModal({ title, message, variant = "warning" }) {
  return new Promise((resolve) => {
    const modalElement = createBaseModal({
      title,
      sizeClass: "modal-dialog-centered",
    });

    const body = modalElement.querySelector(".modal-body");
    const footer = modalElement.querySelector(".modal-footer");

    const alert = document.createElement("div");
    alert.className = `alert alert-${normaliseBootstrapVariant(variant)} mb-0`;
    alert.setAttribute("role", "alert");
    alert.textContent = message;
    body.appendChild(alert);

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "btn btn-primary";
    closeButton.dataset.bsDismiss = "modal";
    closeButton.textContent = "OK";
    footer.appendChild(closeButton);

    openBootstrapModal(modalElement, {
      onHiddenWithoutAction: resolve,
    });
  });
}

function createBaseModal({ title, sizeClass = "modal-dialog-centered" }) {
  const modalId = `cancellationModal-${Date.now()}-${Math.floor(
    Math.random() * 100000,
  )}`;

  const modalElement = document.createElement("div");
  modalElement.className = "modal fade";
  modalElement.id = modalId;
  modalElement.tabIndex = -1;
  modalElement.setAttribute("aria-hidden", "true");

  const dialog = document.createElement("div");
  dialog.className = `modal-dialog ${sizeClass}`;

  const content = document.createElement("div");
  content.className = "modal-content border-0 shadow";

  const header = document.createElement("div");
  header.className = "modal-header";

  const heading = document.createElement("h5");
  heading.className = "modal-title";
  heading.textContent = title || "Order cancellation";

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "btn-close";
  closeButton.dataset.bsDismiss = "modal";
  closeButton.setAttribute("aria-label", "Close");

  const body = document.createElement("div");
  body.className = "modal-body";

  const footer = document.createElement("div");
  footer.className = "modal-footer";

  header.appendChild(heading);
  header.appendChild(closeButton);

  content.appendChild(header);
  content.appendChild(body);
  content.appendChild(footer);

  dialog.appendChild(content);
  modalElement.appendChild(dialog);

  document.body.appendChild(modalElement);

  return modalElement;
}

function openBootstrapModal(
  modalElement,
  { onShown = null, onHiddenWithoutAction = null } = {},
) {
  const ModalConstructor = window.bootstrap?.Modal;

  if (!ModalConstructor) {
    throw new Error(
      "Bootstrap Modal is unavailable. Make sure Bootstrap JavaScript is loaded before order_cancellation.js.",
    );
  }

  const modalInstance = ModalConstructor.getOrCreateInstance(modalElement, {
    backdrop: "static",
    keyboard: false,
  });

  let closedProgrammatically = false;

  modalElement.addEventListener(
    "shown.bs.modal",
    () => {
      if (typeof onShown === "function") {
        onShown();
      }
    },
    { once: true },
  );

  modalElement.addEventListener(
    "hidden.bs.modal",
    () => {
      modalInstance.dispose();
      modalElement.remove();

      if (!closedProgrammatically && typeof onHiddenWithoutAction === "function") {
        onHiddenWithoutAction();
      }
    },
    { once: true },
  );

  modalElement.addEventListener("cancellation-modal:close", () => {
    closedProgrammatically = true;
  });

  modalInstance.show();
}

function closeBootstrapModal(modalElement) {
  const modalInstance = window.bootstrap?.Modal.getInstance(modalElement);

  if (!modalInstance) {
    modalElement.remove();
    return;
  }

  modalElement.dispatchEvent(new CustomEvent("cancellation-modal:close"));
  modalInstance.hide();
}

function normaliseBootstrapVariant(variant) {
  const allowedVariants = new Set([
    "primary",
    "secondary",
    "success",
    "danger",
    "warning",
    "info",
    "light",
    "dark",
  ]);

  if (allowedVariants.has(variant)) {
    return variant;
  }

  return "warning";
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