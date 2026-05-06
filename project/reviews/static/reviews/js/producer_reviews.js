(() => {
  const page = document.getElementById("producerReviewsPage");
  if (!page) return;

  const listEl = document.getElementById("producerReviewsList");
  const errorEl = document.getElementById("producerReviewsError");

  const apiUrl = page.dataset.apiUrl || "/api/reviews/producer/reviews/";
  const replyBaseUrl =
    page.dataset.replyBaseUrl || "/reviews/producer/reviews/";

  function escapeHtml(value = "") {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDate(value) {
    if (!value) return "";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";

    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function renderStars(rating) {
    const safeRating = Math.max(0, Math.min(5, Number(rating) || 0));

    return Array.from({ length: 5 }, (_, index) => {
      const filled = index < safeRating;
      return `<span class="review-star ${filled ? "is-filled" : ""}" aria-hidden="true">★</span>`;
    }).join("");
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  async function parseErrorResponse(response, fallbackMessage) {
    try {
      const data = await response.json();
      return data?.message || data?.detail || fallbackMessage;
    } catch {
      return fallbackMessage;
    }
  }

  function buildReplyUrl(reviewId) {
    const next = encodeURIComponent(window.location.pathname);
    return `${replyBaseUrl}${reviewId}/reply/?next=${next}`;
  }

  function renderEmptyState() {
    listEl.innerHTML = `
      <div class="card border-0 shadow-sm">
        <div class="card-body p-4">
          <h2 class="h5 mb-2">No customer reviews yet</h2>
          <p class="text-muted mb-0">
            Published customer reviews for producer products will appear here.
          </p>
        </div>
      </div>
    `;
  }

  function renderReviewCard(review) {
    const response = review.producer_response;
    const hasResponse = Boolean(response);

    const safeProductName = escapeHtml(review.product_name || "Product");
    const safeTitle = escapeHtml(review.title || "Untitled review");
    const safeText = escapeHtml(review.text || "").replace(/\n/g, "<br>");
    const safeReviewer = escapeHtml(review.reviewer_name || "Customer");
    const safeReviewDate = escapeHtml(formatDate(review.created_at));
    const safeLatestActivity = escapeHtml(formatDate(review.latest_activity_at));
    const rating = Math.max(0, Math.min(5, Number(review.rating) || 0));

    const responseStatus = hasResponse ? escapeHtml(response.status || "") : "";
    const responseDate = hasResponse
      ? escapeHtml(formatDate(response.updated_at))
      : "";

    return `
      <article class="card border-0 shadow-sm producer-review-card">
        <div class="card-body p-4">
          <div class="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-3">
            <div>
              <p class="text-muted mb-1">${safeProductName}</p>
              <h2 class="h5 mb-1">${safeTitle}</h2>

              <div class="small text-muted">
                ${safeReviewer}
                ${safeReviewDate ? ` • ${safeReviewDate}` : ""}
              </div>
            </div>

            <div class="text-lg-end">
              <div class="product-review-rating mb-1"
                   aria-label="${rating} out of 5">
                ${renderStars(rating)}
              </div>

              ${
                safeLatestActivity
                  ? `<div class="small text-muted">Latest activity: ${safeLatestActivity}</div>`
                  : ""
              }
            </div>
          </div>

          <div class="border rounded bg-light p-3 mb-3">
            <p class="mb-0">${safeText}</p>
          </div>

          ${
            hasResponse
              ? `
                <div class="border rounded p-3 mb-3 producer-response-existing">
                  <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
                    <strong>Producer response</strong>
                    <span class="badge ${
                      response.status === "PUB"
                        ? "text-bg-success"
                        : "text-bg-warning"
                    }">
                      ${response.status === "PUB" ? "Replied" : responseStatus}
                    </span>
                  </div>

                  <p class="mb-1">
                    ${escapeHtml(response.text || "").replace(/\n/g, "<br>")}
                  </p>

                  ${
                    responseDate
                      ? `<div class="small text-muted">Updated ${responseDate}</div>`
                      : ""
                  }
                </div>
              `
              : `
                <div class="alert alert-secondary mb-3">
                  No producer response has been added yet.
                </div>
              `
          }

          <div class="d-flex justify-content-end">
            <a class="btn ${hasResponse ? "btn-primary" : "btn-primary"}"
               href="${buildReplyUrl(review.id)}">
              ${hasResponse ? "Edit reply" : "Reply"}
            </a>
          </div>
        </div>
      </article>
    `;
  }

  async function loadReviews() {
    clearError();

    try {
      const response = await fetch(apiUrl, {
        headers: {
          Accept: "application/json",
        },
        credentials: "same-origin",
      });

      if (!response.ok) {
        const message = await parseErrorResponse(
          response,
          "Unable to load reviews.",
        );
        throw new Error(message);
      }

      const data = await response.json();
      const reviews = Array.isArray(data.results) ? data.results : [];

      if (!reviews.length) {
        renderEmptyState();
        return;
      }

      listEl.innerHTML = reviews.map(renderReviewCard).join("");
    } catch (error) {
      listEl.innerHTML = "";
      showError(error.message || "Unable to load reviews.");
    }
  }

  loadReviews();
})();