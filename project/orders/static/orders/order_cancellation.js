const CUSTOMER_ORDER_CANCEL_API_BASE = "/api/orders/customer/orders/";

document.addEventListener("click", async (event) => {
  const cancelBtn = event.target.closest("[data-action='cancel-customer-order']");

  if (!cancelBtn) {
    return;
  }

  event.preventDefault();

  if (cancelBtn.disabled) {
    return;
  }

  const orderId = cancelBtn.dataset.orderId;
  const orderNumber = cancelBtn.dataset.orderNumber || `#${orderId}`;

  if (!orderId) {
    showCancellationFeedback("Order ID is missing.", "danger");
    return;
  }

  const reason = window.prompt(
    `Cancel order ${orderNumber}?\n\nEnter a reason, or leave blank to use the default reason.`,
    "",
  );

  if (reason === null) {
    return;
  }

  await submitCustomerOrderCancellation(cancelBtn, orderId, reason);
});

async function submitCustomerOrderCancellation(button, orderId, reason) {
  const originalText = button.textContent;

  button.disabled = true;
  button.textContent = "Cancelling...";

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

    showCancellationFeedback(
      payload.message || "Order cancelled successfully.",
      "success",
    );

    if (window.OrderHistoryPage?.loadOrders) {
      await window.OrderHistoryPage.loadOrders();
    }

    if (window.OrderHistoryPage?.openOrderDetails) {
      await window.OrderHistoryPage.openOrderDetails(orderId);
    }
  } catch (error) {
    showCancellationFeedback(
      error.message || "Order cancellation failed.",
      "danger",
    );

    button.disabled = false;
    button.textContent = originalText;
  }
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

function showCancellationFeedback(message, variant = "warning") {
  if (!message) {
    return;
  }

  if (typeof window.CartAPI?.showToast === "function") {
    window.CartAPI.showToast(message, {
      title: "Order cancellation",
      variant,
      delay: 3500,
    });
    return;
  }

  const errorBox = document.getElementById("orderDetailError");

  if (errorBox) {
    errorBox.textContent = message;
    errorBox.classList.remove("d-none");

    if (variant === "success") {
      errorBox.classList.remove("alert-danger");
      errorBox.classList.add("alert-success");
    } else {
      errorBox.classList.remove("alert-success");
      errorBox.classList.add("alert-danger");
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