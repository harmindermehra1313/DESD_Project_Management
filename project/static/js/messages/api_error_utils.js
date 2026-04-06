// static/js/messages/api_error_utils.js
(function () {
  function isNonEmptyString(value) {
    return typeof value === "string" && value.trim() !== "";
  }

  function flattenMessages(value) {
    if (Array.isArray(value)) {
      return value
        .flatMap((item) => flattenMessages(item))
        .filter(Boolean);
    }

    if (isNonEmptyString(value)) {
      return [value.trim()];
    }

    if (value && typeof value === "object") {
      const parts = [];

      if (isNonEmptyString(value.detail)) parts.push(value.detail.trim());
      if (isNonEmptyString(value.message)) parts.push(value.message.trim());
      if (isNonEmptyString(value.error)) parts.push(value.error.trim());

      if (Array.isArray(value.non_field_errors)) {
        parts.push(...value.non_field_errors.flatMap((item) => flattenMessages(item)));
      }

      for (const [key, val] of Object.entries(value)) {
        if (["detail", "message", "error", "non_field_errors"].includes(key)) {
          continue;
        }

        if (Array.isArray(val)) {
          for (const item of val) {
            if (isNonEmptyString(item)) {
              parts.push(`${key}: ${item.trim()}`);
            }
          }
        } else if (isNonEmptyString(val)) {
          parts.push(`${key}: ${val.trim()}`);
        }
      }

      return [...new Set(parts)];
    }

    return [];
  }

  function fromPayload(payload, fallback = "Something went wrong. Please try again.") {
    const parts = flattenMessages(payload);
    return parts.length ? parts.join(" ") : fallback;
  }

  async function fromResponse(response, fallback) {
    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      return fallback;
    }

    try {
      const payload = await response.json();
      return fromPayload(payload, fallback);
    } catch (_) {
      return fallback;
    }
  }

  function fromError(error, fallback = "Something went wrong. Please try again.") {
    if (error && typeof error === "object") {
      if (isNonEmptyString(error.userMessage)) return error.userMessage.trim();
      if (isNonEmptyString(error.message)) return error.message.trim();
      if (error.payload) return fromPayload(error.payload, fallback);
    }

    if (isNonEmptyString(error)) return error.trim();
    return fallback;
  }

  window.AppApiErrors = {
    fromPayload,
    fromResponse,
    fromError,
  };
})();