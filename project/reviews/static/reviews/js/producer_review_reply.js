(() => {
  const form = document.getElementById("producerReplyForm");
  if (!form) return;

  const errorBox = document.getElementById("producerReplyError");
  const successBox = document.getElementById("producerReplySuccess");
  const submitBtn = document.getElementById("producerReplySubmitBtn");

  const apiUrl = form.dataset.apiUrl;
  const nextUrl = form.dataset.nextUrl || "/reviews/producer/reviews/";
  const textField = form.elements.text;

  const messages = {
    textRequired: "Enter a response before submitting.",
    textTooLong: "Response must be 2,000 characters or fewer.",
    forbidden: "This review cannot be replied to by this producer account.",
    notFound: "The selected review could not be found.",
    spam: "This response looks like spam or promotional content. Remove links, discount codes, or advertising language and try again.",
    serviceUnavailable:
      "The response service is temporarily unavailable. Please try again later.",
    genericSubmitError:
      "The response could not be submitted at this time. Please try again.",
  };

  function getCookie(name) {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${name}=`));

    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  }

  function escapeHtml(value = "") {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clearMessages() {
    errorBox.innerHTML = "";
    errorBox.classList.add("d-none");
    successBox.textContent = "";
    successBox.classList.add("d-none");

    textField.classList.remove("is-invalid");
    textField.removeAttribute("aria-invalid");
  }

  function showError(message) {
    errorBox.innerHTML = `
      <div class="fw-semibold mb-1">Please review the form.</div>
      <ul class="mb-0 ps-3">
        <li>${escapeHtml(message)}</li>
      </ul>
    `;
    errorBox.classList.remove("d-none");

    textField.classList.add("is-invalid");
    textField.setAttribute("aria-invalid", "true");
  }

  function showSuccess(message) {
    successBox.textContent = message;
    successBox.classList.remove("d-none");
  }

  function getStructuredError(data) {
    if (!data || typeof data !== "object") {
      return null;
    }

    return data.error || data;
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

  function getApiErrorMessage(response, data) {
    const structuredError = getStructuredError(data);
    const code = firstErrorValue(structuredError?.code);
    const backendMessage = firstErrorValue(structuredError?.message);

    if (code === "producer_response_text_required") {
      return messages.textRequired;
    }

    if (code === "producer_response_text_too_long") {
      return messages.textTooLong;
    }

    if (code === "producer_response_spam_detected") {
      return messages.spam;
    }

    if (code === "producer_profile_required") {
      return messages.forbidden;
    }

    if (code === "producer_review_not_found") {
      return messages.notFound;
    }

    if (backendMessage) {
      return backendMessage;
    }

    if (response.status === 403) {
      return messages.forbidden;
    }

    if (response.status === 404) {
      return messages.notFound;
    }

    if (response.status >= 500) {
      return messages.serviceUnavailable;
    }

    return messages.genericSubmitError;
  }

  function validateForm() {
    const text = textField.value.trim();

    if (!text) {
      showError(messages.textRequired);
      return null;
    }

    if (text.length > 2000) {
      showError(messages.textTooLong);
      return null;
    }

    return { text };
  }

  async function submitReply(payload) {
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
    } catch {
      data = null;
    }

    if (!response.ok) {
      throw new Error(getApiErrorMessage(response, data));
    }

    return data;
  }

  textField.addEventListener("input", () => {
    textField.classList.remove("is-invalid");
    textField.removeAttribute("aria-invalid");

    if (!errorBox.classList.contains("d-none")) {
      errorBox.innerHTML = "";
      errorBox.classList.add("d-none");
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessages();

    const payload = validateForm();
    if (!payload) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";

    try {
      const data = await submitReply(payload);

      if (data?.code === "producer_response_sent_for_moderation") {
        successBox.classList.remove("alert-success");
        successBox.classList.add("alert-warning");
        showSuccess("Response submitted and sent for moderation.");
      } else {
        successBox.classList.remove("alert-warning");
        successBox.classList.add("alert-success");
        showSuccess("Response submitted successfully.");
      }

      setTimeout(() => {
        window.location.assign(nextUrl);
      }, 700);
    } catch (error) {
      showError(error.message || messages.genericSubmitError);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit reply";
    }
  });
})();