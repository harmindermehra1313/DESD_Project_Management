/*
  Extra validation layer for producer_dashboard.js.

  Load this file AFTER producer_dashboard.js.

  This file does not require changing producer_dashboard.js.
  It wraps selected global functions and adds safer producer-friendly validation.
*/

(function () {
  "use strict";

  const VALID_PRODUCER_STATUSES = new Set([
    "PEN",
    "PRE",
    "PAC",
    "RFC",
    "SHP",
    "COM",
    "CAN",
  ]);

  const TERMINAL_PRODUCER_STATUSES = new Set(["COM", "CAN"]);

  /*
    Producer cancellation policy:
    - Pending, Preparing, Packaged, and Ready for collection can be cancelled.
    - Shipped, Completed, and Cancelled cannot be cancelled from the producer page.
  */
  const CANCELLABLE_PRODUCER_STATUSES = new Set([
    "PEN",
    "PRE",
    "PAC",
    "RFC",
  ]);

  const NON_CANCELLABLE_PRODUCER_STATUSES = new Set([
    "SHP",
    "COM",
    "CAN",
  ]);

  const CANCELLATION_REASON_MIN_LENGTH = 10;
  const CANCELLATION_REASON_MAX_LENGTH = 250;

  let isStatusSubmitting = false;
  let isProducerOrderCancellationSubmitting = false;
  let isItemCancellationSubmitting = false;

  const originalApplyAllFilters = window.applyAllFilters;
  const originalOpenStatusConfirmModal = window.openStatusConfirmModal;
  const originalChangeStatus = window.changeStatus;
  const originalOpenCancelQuantityModal = window.openCancelQuantityModal;
  const originalConfirmCancelQuantity = window.confirmCancelQuantity;

  /* ============================================================
     Safe helper functions
  ============================================================ */

  function hasFunction(functionName) {
    return typeof window[functionName] === "function";
  }

  async function showValidationMessage({
    title = "Action not available",
    message = "This action cannot continue.",
    variant = "warning",
  } = {}) {
    if (hasFunction("showMessageModal")) {
      await window.showMessageModal({
        title,
        message,
        variant,
      });
      return;
    }

    window.alert(`${title}\n\n${message}`);
  }

  function normaliseReason(reason) {
    return String(reason || "").replace(/\s+/g, " ").trim();
  }

  function getCurrentSelectedSummaryId() {
    try {
      if (typeof selectedSummaryId !== "undefined" && selectedSummaryId) {
        return selectedSummaryId;
      }
    } catch (_error) {
      // Ignore. Fallback below.
    }

    const selectedRow = document.querySelector(".order-row.selected");

    if (!selectedRow || !selectedRow.id) {
      return null;
    }

    return selectedRow.id.replace("row-", "");
  }

  function getSummaryRow(summaryId = getCurrentSelectedSummaryId()) {
    if (!summaryId) return null;
    return document.getElementById(`row-${summaryId}`);
  }

  function getSummaryStatus(summaryId = getCurrentSelectedSummaryId()) {
    const row = getSummaryRow(summaryId);
    return row ? row.getAttribute("data-status") : null;
  }

  function getSummaryStatusLabel(statusCode) {
    if (hasFunction("getProducerStatusInfo")) {
      const info = window.getProducerStatusInfo(statusCode);
      return info?.text || statusCode || "Unknown";
    }

    const fallbackLabels = {
      PEN: "Pending",
      PRE: "Preparing",
      PAC: "Packaged",
      RFC: "Ready for collection",
      SHP: "Shipped",
      COM: "Completed",
      CAN: "Cancelled",
    };

    return fallbackLabels[statusCode] || statusCode || "Unknown";
  }

  function isValidProducerStatus(statusCode) {
    return VALID_PRODUCER_STATUSES.has(statusCode);
  }

  function safeParseAllowedStatuses(rowElement) {
    if (!rowElement) return [];

    try {
      const parsedStatuses = JSON.parse(
        rowElement.getAttribute("data-allowed-statuses") || "[]",
      );

      if (!Array.isArray(parsedStatuses)) {
        return [];
      }

      return parsedStatuses.filter((status) => {
        return (
          status &&
          typeof status.value === "string" &&
          typeof status.label === "string" &&
          isValidProducerStatus(status.value)
        );
      });
    } catch (error) {
      console.error("Invalid allowed status JSON:", error);
      return [];
    }
  }

  function getAllowedStatusesForSummary(summaryId = getCurrentSelectedSummaryId()) {
    return safeParseAllowedStatuses(getSummaryRow(summaryId));
  }

  function validateCancellationReason(reason) {
    const cleanReason = normaliseReason(reason);

    if (!cleanReason) {
      return {
        valid: false,
        message: "Enter a reason before continuing.",
      };
    }

    if (cleanReason.length < CANCELLATION_REASON_MIN_LENGTH) {
      return {
        valid: false,
        message: `Enter a clearer reason. Use at least ${CANCELLATION_REASON_MIN_LENGTH} characters.`,
      };
    }

    if (cleanReason.length > CANCELLATION_REASON_MAX_LENGTH) {
      return {
        valid: false,
        message: `Reason is too long. Use ${CANCELLATION_REASON_MAX_LENGTH} characters or fewer.`,
      };
    }

    return {
      valid: true,
      reason: cleanReason,
    };
  }

  function validateDateFilters() {
    const fromDateInput = document.getElementById("filterDateFrom");
    const toDateInput = document.getElementById("filterDateTo");

    const fromDate = fromDateInput?.value || "";
    const toDate = toDateInput?.value || "";

    fromDateInput?.classList.remove("is-invalid");
    toDateInput?.classList.remove("is-invalid");

    const existingError = document.getElementById("dateFilterValidationMessage");

    if (existingError) {
      existingError.remove();
    }

    if (fromDate && toDate && fromDate > toDate) {
      fromDateInput?.classList.add("is-invalid");
      toDateInput?.classList.add("is-invalid");

      const message = document.createElement("div");
      message.id = "dateFilterValidationMessage";
      message.className = "invalid-feedback d-block small mt-1";
      message.textContent = "The start due date cannot be after the end due date.";

      toDateInput?.insertAdjacentElement("afterend", message);

      return false;
    }

    return true;
  }

  function validateStatusChangeRequest(newStatus) {
    const summaryId = getCurrentSelectedSummaryId();

    if (!summaryId) {
      return {
        valid: false,
        title: "No order selected",
        message: "Select an order before changing its status.",
        variant: "warning",
      };
    }

    if (!isValidProducerStatus(newStatus)) {
      return {
        valid: false,
        title: "Invalid status",
        message: "The selected status is not recognised. Refresh the page and try again.",
        variant: "danger",
      };
    }

    const row = getSummaryRow(summaryId);

    if (!row) {
      return {
        valid: false,
        title: "Order not found",
        message: "The selected order could not be found on this page. Refresh the page and try again.",
        variant: "danger",
      };
    }

    const currentStatus = getSummaryStatus(summaryId);

    if (TERMINAL_PRODUCER_STATUSES.has(currentStatus)) {
      return {
        valid: false,
        title: "Status cannot be changed",
        message: `This producer section is already ${getSummaryStatusLabel(currentStatus).toLowerCase()}. No further status update is allowed.`,
        variant: "warning",
      };
    }

    const allowedStatuses = getAllowedStatusesForSummary(summaryId);
    const isAllowed = allowedStatuses.some((status) => status.value === newStatus);

    if (!isAllowed) {
      return {
        valid: false,
        title: "Status no longer available",
        message: "This status update is not available for the selected order. Refresh the page and check the current status.",
        variant: "warning",
      };
    }

    return { valid: true };
  }

  function validateProducerCancellationRequest(summaryId, activeQuantity = null) {
    const row = getSummaryRow(summaryId);

    if (!row) {
      return {
        valid: false,
        title: "Order not found",
        message: "The selected producer order could not be found. Refresh the page and try again.",
        variant: "danger",
      };
    }

    const status = row.getAttribute("data-status");

    if (!isValidProducerStatus(status)) {
      return {
        valid: false,
        title: "Invalid order status",
        message: "This producer order has an invalid status. Refresh the page and try again.",
        variant: "danger",
      };
    }

    if (NON_CANCELLABLE_PRODUCER_STATUSES.has(status)) {
      return {
        valid: false,
        title: "Cancellation not allowed",
        message: `This producer section is already ${getSummaryStatusLabel(status).toLowerCase()}. It cannot be cancelled from the producer dashboard.`,
        variant: "warning",
      };
    }

    if (!CANCELLABLE_PRODUCER_STATUSES.has(status)) {
      return {
        valid: false,
        title: "Cancellation not available",
        message: "This producer section cannot be cancelled automatically at its current status.",
        variant: "warning",
      };
    }

    if (activeQuantity !== null) {
      const parsedActiveQuantity = Number.parseInt(activeQuantity, 10);

      if (!Number.isInteger(parsedActiveQuantity) || parsedActiveQuantity <= 0) {
        return {
          valid: false,
          title: "No active quantity",
          message: "This item has no active quantity left to cancel.",
          variant: "warning",
        };
      }
    }

    return { valid: true };
  }

 

  window.parseAllowedStatuses = function parseAllowedStatusesWithValidation(rowElement) {
    return safeParseAllowedStatuses(rowElement);
  };



  if (typeof originalApplyAllFilters === "function") {
    window.applyAllFilters = function applyAllFiltersWithValidation(...args) {
      if (!validateDateFilters()) {
        return;
      }

      return originalApplyAllFilters.apply(this, args);
    };
  }



  if (typeof originalOpenStatusConfirmModal === "function") {
    window.openStatusConfirmModal = async function openStatusConfirmModalWithValidation(
      statusValue,
      statusLabel,
    ) {
      const validation = validateStatusChangeRequest(statusValue);

      if (!validation.valid) {
        await showValidationMessage(validation);
        return;
      }

      return originalOpenStatusConfirmModal.call(this, statusValue, statusLabel);
    };
  }

  if (typeof originalChangeStatus === "function") {
    window.changeStatus = async function changeStatusWithValidation(newStatus) {
      if (isStatusSubmitting) return;

      const validation = validateStatusChangeRequest(newStatus);

      if (!validation.valid) {
        await showValidationMessage(validation);
        return;
      }

      isStatusSubmitting = true;

      try {
        return await originalChangeStatus.call(this, newStatus);
      } finally {
        isStatusSubmitting = false;
      }
    };
  }


  if (typeof originalOpenCancelQuantityModal === "function") {
    window.openCancelQuantityModal = async function openCancelQuantityModalWithValidation(
      itemId,
      productName,
      summaryId,
      activeQuantity,
      cancelWholeItem = false,
    ) {
      const validation = validateProducerCancellationRequest(
        summaryId,
        activeQuantity,
      );

      if (!validation.valid) {
        await showValidationMessage(validation);
        return;
      }

      return originalOpenCancelQuantityModal.call(
        this,
        itemId,
        productName,
        summaryId,
        activeQuantity,
        cancelWholeItem,
      );
    };
  }



  window.openCancelQuantityReviewModal = function openCancelQuantityReviewModalWithValidation() {
    if (hasFunction("clearCancelQuantityFormError")) {
      window.clearCancelQuantityFormError();
    }

    const quantityInput = document.getElementById("cancelQuantityInput");
    const reasonInput = document.getElementById("cancelQuantityReason");

    let activeQuantity = 0;

    try {
      if (typeof pendingCancelActiveQuantity !== "undefined") {
        activeQuantity = Number.parseInt(pendingCancelActiveQuantity, 10) || 0;
      }
    } catch (_error) {
      activeQuantity = 0;
    }

    const quantityToCancel = Number.parseInt(
      (quantityInput?.value || "").trim(),
      10,
    );

    const reason = normaliseReason(reasonInput?.value || "");

    if (!Number.isInteger(quantityToCancel) || quantityToCancel <= 0) {
      if (hasFunction("showCancelQuantityFormError")) {
        window.showCancelQuantityFormError(
          "Enter a whole number greater than 0 before continuing.",
        );
      }
      return;
    }

    if (activeQuantity <= 0) {
      if (hasFunction("showCancelQuantityFormError")) {
        window.showCancelQuantityFormError(
          "This item has no active quantity left to cancel.",
        );
      }
      return;
    }

    if (quantityToCancel > activeQuantity) {
      if (hasFunction("showCancelQuantityFormError")) {
        window.showCancelQuantityFormError(
          `Only ${activeQuantity} active item(s) remain. The cancellation quantity cannot be higher than this.`,
        );
      }
      return;
    }

    const reasonValidation = validateCancellationReason(reason);

    if (!reasonValidation.valid) {
      if (hasFunction("showCancelQuantityFormError")) {
        window.showCancelQuantityFormError(reasonValidation.message);
      }
      return;
    }

    try {
      pendingCancelQuantity = quantityToCancel;
      pendingCancelReason = reasonValidation.reason;
    } catch (_error) {
      showValidationMessage({
        title: "Cancellation details missing",
        message: "The cancellation details could not be saved. Refresh the page and try again.",
        variant: "danger",
      });
      return;
    }

    const remainingQuantity = activeQuantity - quantityToCancel;

    if (hasFunction("setElementText")) {
      window.setElementText("reviewCancelProductName", pendingCancelProductName);
      window.setElementText("reviewCancelActiveQty", activeQuantity);
      window.setElementText("reviewCancelQty", quantityToCancel);
      window.setElementText("reviewRemainingQty", remainingQuantity);
      window.setElementText("reviewCancelReason", reasonValidation.reason);
    }

    const firstModalElement = document.getElementById("cancelQuantityModal");
    const reviewModalElement = document.getElementById("cancelQuantityReviewModal");

    const firstModal = hasFunction("getModalInstance")
      ? window.getModalInstance(firstModalElement)
      : null;

    const reviewModal = hasFunction("getModalInstance")
      ? window.getModalInstance(reviewModalElement)
      : null;

    if (firstModal) {
      firstModal.hide();
    }

    if (!reviewModal) {
      showValidationMessage({
        title: "Review form unavailable",
        message: "The final cancellation check could not be opened. Refresh the page and try again.",
        variant: "danger",
      });
      return;
    }

    reviewModal.show();
  };



  if (typeof originalConfirmCancelQuantity === "function") {
    window.confirmCancelQuantity = async function confirmCancelQuantityWithValidation() {
      if (isItemCancellationSubmitting) return;

      let reason = "";

      try {
        reason = typeof pendingCancelReason !== "undefined"
          ? pendingCancelReason
          : "";
      } catch (_error) {
        reason = "";
      }

      const reasonValidation = validateCancellationReason(reason);

      if (!reasonValidation.valid) {
        await showValidationMessage({
          title: "Reason required",
          message: reasonValidation.message,
          variant: "warning",
        });
        return;
      }

      try {
        pendingCancelReason = reasonValidation.reason;
      } catch (_error) {
        // Ignore. Existing function will still perform its own validation.
      }

      isItemCancellationSubmitting = true;

      try {
        return await originalConfirmCancelQuantity.call(this);
      } finally {
        isItemCancellationSubmitting = false;
      }
    };
  }



  window.cancelProducerOrder = async function cancelProducerOrderWithValidation(summaryId) {
    if (isProducerOrderCancellationSubmitting) return;

    isProducerOrderCancellationSubmitting = true;

    try {
      const validation = validateProducerCancellationRequest(summaryId);

      if (!validation.valid) {
        await showValidationMessage(validation);
        return;
      }

      if (!hasFunction("showTextInputModal")) {
        await showValidationMessage({
          title: "Cancellation form unavailable",
          message: "The cancellation form could not be opened. Refresh the page and try again.",
          variant: "danger",
        });
        return;
      }

      const reason = await window.showTextInputModal({
        title: "Cancel producer order",
        message:
          "Use this only when this producer section cannot be fulfilled. The system will handle any card refund or cash-order adjustment that applies.",
        label: "Reason for cancellation",
        placeholder: "Example: unable to fulfil this producer order after stock check.",
        confirmText: "Review cancellation",
      });

      if (reason === null) return;

      const reasonValidation = validateCancellationReason(reason);

      if (!reasonValidation.valid) {
        await showValidationMessage({
          title: "Reason required",
          message: reasonValidation.message,
          variant: "warning",
        });
        return;
      }

      const cleanReason = reasonValidation.reason;
      const currentStatus = getSummaryStatus(summaryId);

      if (!hasFunction("showConfirmModal")) {
        await showValidationMessage({
          title: "Confirmation unavailable",
          message: "The final confirmation box could not be opened. Refresh the page and try again.",
          variant: "danger",
        });
        return;
      }

      const confirmed = await window.showConfirmModal({
        title: "Final cancellation check",
        message:
          "This will cancel this producer section and update the customer payment record where needed.",
        details: [
          { label: "Current status", value: getSummaryStatusLabel(currentStatus) },
          { label: "Reason", value: cleanReason },
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

      const secondValidation = validateProducerCancellationRequest(summaryId);

      if (!secondValidation.valid) {
        await showValidationMessage(secondValidation);
        return;
      }

      if (!hasFunction("getCsrfToken")) {
        await showValidationMessage({
          title: "Security check failed",
          message: "The page security token helper was not found. Refresh the page and try again.",
          variant: "danger",
        });
        return;
      }

      const csrfToken = window.getCsrfToken();

      if (!csrfToken) {
        await showValidationMessage({
          title: "Security check failed",
          message: "The page security token was not found. Refresh the page and try again.",
          variant: "danger",
        });
        return;
      }

      const response = await fetch(`/accounts/cancel-producer-order/${summaryId}/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: cleanReason }),
      });

      let data = {};

      try {
        data = await response.json();
      } catch (_error) {
        data = {};
      }

      if (!response.ok) {
        await showValidationMessage({
          title: "Producer order could not be cancelled",
          message:
            data.error ||
            "The producer order could not be cancelled. Refresh the page and check the current status.",
          variant: "danger",
        });
        return;
      }

      const successMessage = hasFunction("getCancellationCompletionMessage")
        ? window.getCancellationCompletionMessage(data.refund, "producer_order")
        : "This producer section has been cancelled.";

      const refundDetails = hasFunction("getRefundDetails")
        ? window.getRefundDetails(data.refund)
        : [];

      if (hasFunction("showMessageModal")) {
        await window.showMessageModal({
          title: "Producer order cancelled",
          message: successMessage,
          details: [
            ...refundDetails,
            "The page will refresh and reopen this order.",
          ],
          variant: "success",
          buttonText: "Return to order",
        });
      }

      if (hasFunction("reloadAndReopenSummary")) {
        window.reloadAndReopenSummary(summaryId);
      } else {
        window.location.reload();
      }
    } catch (error) {
      console.error("Error cancelling producer order:", error);

      await showValidationMessage({
        title: "Network problem",
        message:
          "The producer order cancellation could not be sent. Check the connection and try again.",
        variant: "danger",
      });
    } finally {
      isProducerOrderCancellationSubmitting = false;
    }
  };


  window.ProducerDashboardValidation = {
    validateDateFilters,
    validateCancellationReason,
    validateStatusChangeRequest,
    validateProducerCancellationRequest,
    getSummaryStatus,
    getSummaryStatusLabel,
  };


function keepCancelledOrdersHiddenByDefault() {
  const cancelledFilter = document.getElementById("filterCan");

  if (cancelledFilter) {
    cancelledFilter.checked = false;
  }
}

const originalClearFilters = window.clearFilters;

if (typeof originalClearFilters === "function") {
  window.clearFilters = function clearFiltersWithCancelledHidden(...args) {
    const result = originalClearFilters.apply(this, args);

    keepCancelledOrdersHiddenByDefault();

    if (typeof window.applyAllFilters === "function") {
      window.applyAllFilters(true);
    }

    return result;
  };
}

document.addEventListener("DOMContentLoaded", () => {
  keepCancelledOrdersHiddenByDefault();

  if (typeof window.applyAllFilters === "function") {
    window.applyAllFilters(true);
  }
});
})();