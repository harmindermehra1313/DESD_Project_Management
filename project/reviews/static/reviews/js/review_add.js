(() => {
  const form = document.getElementById("reviewCreateForm");
  if (!form) return;

  const errorBox = document.getElementById("reviewFormError");
  const successBox = document.getElementById("reviewFormSuccess");
  const submitBtn = document.getElementById("reviewSubmitBtn");
  const apiUrl = form.dataset.apiUrl || "/api/reviews/";

  const fields = {
    title: form.elements.title,
    rating: form.elements.rating,
    text: form.elements.text,
    anonymous: form.elements.anonymous,
    orderId: form.elements.order_id,
    orderItemId: form.elements.order_item_id,
    productId: form.elements.product_id,
    next: form.elements.next,
    popup: form.elements.popup,
  };

  const messages = {
    genericSubmitError:
      "The review could not be submitted at this time. Please try again.",
    genericValidationError:
      "Please correct the highlighted fields and try again.",
    sessionExpired:
      "The session has expired. Sign in again and submit the review once more.",
    forbidden: "This review cannot be submitted for the selected order item.",
    notFound:
      "The selected order item could not be found. Refresh the page and try again.",
    duplicateOrInvalid:
      "This review cannot be submitted. A review may already exist, or the item may no longer be eligible.",
    rateLimited:
      "Too many submission attempts were made. Please wait a moment and try again.",
    serviceUnavailable:
      "The review service is temporarily unavailable. Please try again later.",
    invalidSelection:
      "The selected review item is invalid. Refresh the page and try again.",
    titleRequired: "Enter a review title.",
    titleTooLong:
      "Enter a shorter review title. A maximum of 120 characters is allowed.",
    ratingRequired: "Select a rating between 1 and 5.",
    ratingInvalid: "Select a whole-number rating between 1 and 5.",
    textRequired: "Enter review details before submitting.",
  };

  function getCookie(name) {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${name}=`));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  }

  function getFeedbackElement(field) {
    if (!field) return null;

    let feedback = field.parentElement?.querySelector(
      ".invalid-feedback[data-generated='true']",
    );
    if (feedback) return feedback;

    feedback = document.createElement("div");
    feedback.className = "invalid-feedback";
    feedback.dataset.generated = "true";

    if (field.type === "checkbox") {
      field.closest(".form-check")?.appendChild(feedback);
    } else {
      field.parentElement?.appendChild(feedback);
    }

    return feedback;
  }

  function setFieldError(field, message) {
    if (!field) return;
    field.classList.add("is-invalid");
    field.setAttribute("aria-invalid", "true");

    const feedback = getFeedbackElement(field);
    if (feedback) {
      feedback.textContent = message;
      feedback.style.display = "block";
    }
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove("is-invalid");
    field.removeAttribute("aria-invalid");

    const feedback = getFeedbackElement(field);
    if (feedback) {
      feedback.textContent = "";
      feedback.style.display = "";
    }
  }

  function clearAllFieldErrors() {
    Object.values(fields).forEach((field) => {
      if (field instanceof HTMLElement) {
        clearFieldError(field);
      }
    });
  }

  function clearMessages() {
    clearAllFieldErrors();
    errorBox.innerHTML = "";
    errorBox.classList.add("d-none");
    successBox.classList.add("d-none");
  }

  function showFormErrors(items) {
    const uniqueItems = [...new Set(items.filter(Boolean))];
    if (!uniqueItems.length) return;

    errorBox.innerHTML = `
      <div class="fw-semibold mb-1">Please review the form.</div>
      <ul class="mb-0 ps-3">
        ${uniqueItems.map((item) => `<li>${item}</li>`).join("")}
      </ul>
    `;
    errorBox.classList.remove("d-none");
  }

  function parsePositiveInteger(value) {
    const number = Number(value);
    return Number.isInteger(number) && number > 0 ? number : null;
  }

  function validateForm() {
    clearAllFieldErrors();

    const title = fields.title.value.trim();
    const text = fields.text.value.trim();
    const ratingRaw = fields.rating.value.trim();

    const orderId = parsePositiveInteger(fields.orderId.value);
    const orderItemId = parsePositiveInteger(fields.orderItemId.value);
    const productId = parsePositiveInteger(fields.productId.value);

    const formErrors = [];

    if (!orderId || !orderItemId || !productId) {
      formErrors.push(messages.invalidSelection);
    }

    if (!title) {
      setFieldError(fields.title, messages.titleRequired);
      formErrors.push(messages.titleRequired);
    } else if (title.length > 120) {
      setFieldError(fields.title, messages.titleTooLong);
      formErrors.push(messages.titleTooLong);
    }

    if (!ratingRaw) {
      setFieldError(fields.rating, messages.ratingRequired);
      formErrors.push(messages.ratingRequired);
    } else {
      const rating = Number(ratingRaw);
      const isWholeNumber = Number.isInteger(rating);
      const inRange = rating >= 1 && rating <= 5;

      if (!isWholeNumber || !inRange) {
        setFieldError(fields.rating, messages.ratingInvalid);
        formErrors.push(messages.ratingInvalid);
      }
    }

    if (!text) {
      setFieldError(fields.text, messages.textRequired);
      formErrors.push(messages.textRequired);
    }

    if (formErrors.length) {
      showFormErrors(formErrors);
      return null;
    }

    return {
      order_id: orderId,
      order_item_id: orderItemId,
      product_id: productId,
      title,
      text,
      rating: Number(ratingRaw),
      anonymous: fields.anonymous.checked,
    };
  }

  function firstErrorValue(value) {
    if (value === null || value === undefined) {
      return "";
    }

    if (typeof value === "string") {
      return value;
    }

    if (Array.isArray(value)) {
      return firstErrorValue(value[0]);
    }

    return String(value);
  }

  function getStructuredError(data) {
    if (!data || typeof data !== "object") {
      return null;
    }

    return data.error || data;
  }

  function getStructuredErrorCode(data) {
    const structuredError = getStructuredError(data);
    return firstErrorValue(structuredError?.code);
  }

  function getStructuredErrorMessage(data) {
    const structuredError = getStructuredError(data);
    return firstErrorValue(structuredError?.message);
  }

  function getStructuredErrorData(data) {
    const structuredError = getStructuredError(data);
    return structuredError?.data && typeof structuredError.data === "object"
      ? structuredError.data
      : {};
  }

  function normaliseErrorList(value) {
    if (!value) {
      return [];
    }

    if (typeof value === "string") {
      return [value];
    }

    if (Array.isArray(value)) {
      return value.flatMap((item) => normaliseErrorList(item));
    }

    if (typeof value === "object") {
      return Object.values(value).flatMap((item) => normaliseErrorList(item));
    }

    return [String(value)];
  }

  function getReviewApiErrorMessage(response, data) {
    const structuredError = getStructuredError(data);
    const code = getStructuredErrorCode(data);
    const details = getStructuredErrorData(data);

    if (code === "review_customer_profile_required") {
      return "A customer profile is required before a review can be submitted.";
    }

    if (code === "review_spam_detected") {
      const reasons = Array.isArray(details.reasons) ? details.reasons : [];

      if (reasons.length) {
        return "This review looks like spam or promotional content. Remove links, discount codes, or advertising language and try again.";
      }

      return "This review looks like spam or promotional content. Please revise it and try again.";
    }

    if (code === "review_not_allowed") {
      return messages.forbidden;
    }

    if (code === "review_order_item_not_found") {
      return messages.notFound;
    }

    if (code === "review_item_not_eligible") {
      return messages.duplicateOrInvalid;
    }

    const backendMessage = getStructuredErrorMessage(data);
    if (backendMessage) {
      return backendMessage;
    }

    if (response.status === 401) {
      return messages.sessionExpired;
    }

    if (response.status === 403) {
      return messages.forbidden;
    }

    if (response.status === 404) {
      return messages.notFound;
    }

    if (response.status === 409) {
      return messages.duplicateOrInvalid;
    }

    if (response.status === 429) {
      return messages.rateLimited;
    }

    if (response.status >= 500) {
      return messages.serviceUnavailable;
    }

    return messages.genericSubmitError;
  }

  function applyFieldErrors(data) {
    const fieldMappings = {
      title: {
        field: fields.title,
        fallback: messages.titleRequired,
      },
      rating: {
        field: fields.rating,
        fallback: messages.ratingInvalid,
      },
      text: {
        field: fields.text,
        fallback: messages.textRequired,
      },
    };

    const formErrors = [];

    Object.entries(fieldMappings).forEach(([fieldName, config]) => {
      const fieldErrors = normaliseErrorList(data?.[fieldName]);

      if (fieldErrors.length) {
        setFieldError(config.field, fieldErrors[0] || config.fallback);
        formErrors.push(fieldErrors[0] || config.fallback);
      }
    });

    const selectionErrors = [
      ...normaliseErrorList(data?.order_id),
      ...normaliseErrorList(data?.order_item_id),
      ...normaliseErrorList(data?.product_id),
    ];

    if (selectionErrors.length) {
      formErrors.push(messages.invalidSelection);
    }

    return formErrors;
  }
  function handleApiError(response, data) {
    const fieldErrors = applyFieldErrors(data);

    if (fieldErrors.length) {
      showFormErrors(fieldErrors);
      return;
    }

    const message = getReviewApiErrorMessage(response, data);
    showFormErrors([message]);
  }

  async function submitReview(payload) {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      handleApiError(response, data);
      throw new Error("submission_failed");
    }

    return data;
  }

  [fields.title, fields.rating, fields.text].forEach((field) => {
    field?.addEventListener("input", () => {
      clearFieldError(field);
      if (!errorBox.classList.contains("d-none")) {
        errorBox.classList.add("d-none");
        errorBox.innerHTML = "";
      }
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessages();

    const payload = validateForm();
    if (!payload) {
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";

    try {
      const data = await submitReview(payload);

      successBox.textContent =
        data?.code === "review_submitted_for_moderation"
          ? "Review submitted and sent for moderation."
          : "Review submitted successfully.";

      if (
        data?.code === "review_submitted_for_moderation" ||
        data?.is_flagged
      ) {
        successBox.classList.remove("alert-success");
        successBox.classList.add("alert-warning");
      } else {
        successBox.classList.remove("alert-warning");
        successBox.classList.add("alert-success");
      }

      successBox.classList.remove("d-none");

      const nextUrl = fields.next.value || "/orders/history/";
      const popupRequested = fields.popup.value === "1";

      setTimeout(() => {
        try {
          if (popupRequested && window.opener && !window.opener.closed) {
            window.opener.dispatchEvent(
              new CustomEvent("reviews:refresh", {
                detail: { productId: payload.product_id },
              }),
            );
            window.opener.location.assign(nextUrl);
            window.close();
            return;
          }
        } catch (error) {
          // Fallback to same-window redirect below.
        }

        window.location.assign(nextUrl);
      }, 700);
    } catch (error) {
      // User-facing message already handled above.
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit review";
    }
  });
})();
