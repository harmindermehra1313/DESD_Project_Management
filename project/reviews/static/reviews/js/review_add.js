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
    genericSubmitError: "The review could not be submitted at this time. Please try again.",
    genericValidationError: "Please correct the highlighted fields and try again.",
    sessionExpired: "The session has expired. Sign in again and submit the review once more.",
    forbidden: "This review cannot be submitted for the selected order item.",
    notFound: "The selected order item could not be found. Refresh the page and try again.",
    duplicateOrInvalid: "This review cannot be submitted. A review may already exist, or the item may no longer be eligible.",
    rateLimited: "Too many submission attempts were made. Please wait a moment and try again.",
    serviceUnavailable: "The review service is temporarily unavailable. Please try again later.",
    invalidSelection: "The selected review item is invalid. Refresh the page and try again.",
    titleRequired: "Enter a review title.",
    titleTooLong: "Enter a shorter review title. A maximum of 120 characters is allowed.",
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

    let feedback = field.parentElement?.querySelector(".invalid-feedback[data-generated='true']");
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

  function handleApiError(response, data) {
    const formErrors = [];

    if (response.status === 400 || response.status === 422) {
      const hasTitleError = Array.isArray(data?.title) || typeof data?.title === "string";
      const hasRatingError = Array.isArray(data?.rating) || typeof data?.rating === "string";
      const hasTextError = Array.isArray(data?.text) || typeof data?.text === "string";
      const hasSelectionError =
        Array.isArray(data?.order_id) ||
        Array.isArray(data?.order_item_id) ||
        Array.isArray(data?.product_id) ||
        typeof data?.order_id === "string" ||
        typeof data?.order_item_id === "string" ||
        typeof data?.product_id === "string";

      if (hasTitleError) {
        setFieldError(fields.title, messages.titleRequired);
        formErrors.push(messages.titleRequired);
      }

      if (hasRatingError) {
        setFieldError(fields.rating, messages.ratingInvalid);
        formErrors.push(messages.ratingInvalid);
      }

      if (hasTextError) {
        setFieldError(fields.text, messages.textRequired);
        formErrors.push(messages.textRequired);
      }

      if (hasSelectionError) {
        formErrors.push(messages.invalidSelection);
      }

      if (!hasTitleError && !hasRatingError && !hasTextError && !hasSelectionError) {
        formErrors.push(messages.duplicateOrInvalid);
      }

      showFormErrors(formErrors);
      return;
    }

    if (response.status === 401) {
      showFormErrors([messages.sessionExpired]);
      return;
    }

    if (response.status === 403) {
      showFormErrors([messages.forbidden]);
      return;
    }

    if (response.status === 404) {
      showFormErrors([messages.notFound]);
      return;
    }

    if (response.status === 409) {
      showFormErrors([messages.duplicateOrInvalid]);
      return;
    }

    if (response.status === 429) {
      showFormErrors([messages.rateLimited]);
      return;
    }

    if (response.status >= 500) {
      showFormErrors([messages.serviceUnavailable]);
      return;
    }

    showFormErrors([messages.genericSubmitError]);
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
      await submitReview(payload);

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