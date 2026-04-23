(() => {
  function initProductReviews() {
    const root = document.getElementById("productDetailPage");
    if (!root) return;

    const productId = Number(root.dataset.productId ?? "0");

    const reviewsSummaryEl = document.getElementById("productReviewsSummary");
    const reviewsListEl = document.getElementById("productReviewsList");
    const reviewsMetaEl = document.getElementById("productReviewsMeta");
    const reviewsAverageEl = document.getElementById("productReviewsAverage");
    const reviewsBreakdownEl = document.getElementById("productReviewsBreakdown");

    if (!reviewsSummaryEl || !reviewsListEl) return;

    function escapeHtml(value = "") {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function formatReviewDate(value) {
      if (!value) return "";

      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "";

      return new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(date);
    }

    function renderReviewStars(rating) {
      const safeRating = Math.max(0, Math.min(5, Number(rating) || 0));

      return Array.from({ length: 5 }, (_, index) => {
        const filled = index < safeRating;
        return `<span class="review-star ${filled ? "is-filled" : ""}" aria-hidden="true">★</span>`;
      }).join("");
    }

    function renderReviewSummary(summary) {
      const reviewCount = Number(summary?.review_count ?? 0);
      const averageRating = Number(summary?.average_rating ?? 0);

      if (reviewCount <= 0) {
        reviewsSummaryEl.textContent = "No reviews yet.";
        reviewsMetaEl?.classList.add("d-none");
        reviewsBreakdownEl?.classList.add("d-none");
        return;
      }

      reviewsSummaryEl.textContent =
        `${averageRating.toFixed(1)} / 5 from ${reviewCount} review${reviewCount === 1 ? "" : "s"}`;

      if (reviewsAverageEl) {
        reviewsAverageEl.textContent = averageRating.toFixed(1);
      }

      reviewsMetaEl?.classList.remove("d-none");
    }

    function renderReviewBreakdown(summary) {
      if (!reviewsBreakdownEl) return;

      const reviewCount = Number(summary?.review_count ?? 0);
      const breakdown = summary?.rating_breakdown || {};

      if (reviewCount <= 0) {
        reviewsBreakdownEl.classList.add("d-none");
        reviewsBreakdownEl.innerHTML = "";
        return;
      }

      const rows = [5, 4, 3, 2, 1].map((rating) => {
        const count = Number(breakdown[String(rating)] ?? 0);
        const width = reviewCount > 0 ? (count / reviewCount) * 100 : 0;

        return `
          <div class="review-breakdown-row">
            <div class="review-breakdown-label">${rating}★</div>
            <div class="review-breakdown-bar">
              <div class="review-breakdown-bar-fill" style="width: ${width}%"></div>
            </div>
            <div class="review-breakdown-count">${count}</div>
          </div>
        `;
      });

      reviewsBreakdownEl.innerHTML = rows.join("");
      reviewsBreakdownEl.classList.remove("d-none");
    }

    function renderEmptyState() {
      reviewsListEl.innerHTML = `
        <div class="product-review-empty">
          <div class="product-review-empty-icon">☆</div>
          <div>
            <h3 class="h6 mb-1">No published reviews yet</h3>
            <p class="mb-0 text-muted">Submitted reviews will appear here once available.</p>
          </div>
        </div>
      `;
    }

    function renderReviewerBadges(review) {
      const badges = [];

      if (review?.verified_purchase) {
        badges.push(
          `<span class="product-review-badge product-review-badge--verified">
            <i class="bi bi-patch-check-fill" aria-hidden="true"></i>
            Verified purchase
          </span>`
        );
      }

      if (review?.anonymous) {
        badges.push(
          `<span class="product-review-badge product-review-badge--anonymous">
            Anonymous
          </span>`
        );
      }

      return badges.join("");
    }

    function renderReviews(reviews) {
      if (!Array.isArray(reviews) || !reviews.length) {
        renderEmptyState();
        return;
      }

      reviewsListEl.innerHTML = reviews
        .map((review) => {
          const safeTitle = escapeHtml(review.title || "Untitled review");
          const safeText = escapeHtml(review.text || "").replace(/\n/g, "<br>");
          const safeReviewer = escapeHtml(review.reviewer_name || "Verified Customer");
          const safeDate = escapeHtml(formatReviewDate(review.created_at));
          const ratingValue = Math.max(0, Math.min(5, Number(review.rating) || 0));
          const badgeMarkup = renderReviewerBadges(review);

          return `
            <article class="product-review-card">
              <div class="product-review-card-top">
                <div>
                  <h3 class="product-review-title">${safeTitle}</h3>

                  <div class="product-review-meta">
                    <span class="product-review-author">${safeReviewer}</span>
                    ${safeDate ? `<span class="product-review-sep">•</span><span>${safeDate}</span>` : ""}
                  </div>

                  ${badgeMarkup ? `<div class="product-review-badges">${badgeMarkup}</div>` : ""}
                </div>

                <div class="product-review-rating" aria-label="${ratingValue} out of 5">
                  ${renderReviewStars(ratingValue)}
                </div>
              </div>

              <p class="product-review-text mb-0">${safeText}</p>
            </article>
          `;
        })
        .join("");
    }

    async function loadReviews() {
      if (!Number.isInteger(productId) || productId <= 0) {
        reviewsSummaryEl.textContent = "Reviews are unavailable.";
        reviewsListEl.innerHTML = "";
        reviewsMetaEl?.classList.add("d-none");
        reviewsBreakdownEl?.classList.add("d-none");
        return;
      }

      try {
        const response = await fetch(`/api/reviews/products/${productId}/reviews/`, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });

        if (!response.ok) {
          throw new Error(`Unable to load reviews. HTTP ${response.status}`);
        }

        const data = await response.json();
        renderReviewSummary(data.summary || {});
        renderReviewBreakdown(data.summary || {});
        renderReviews(data.results || []);
      } catch (err) {
        reviewsSummaryEl.textContent = "Reviews are unavailable right now.";
        reviewsMetaEl?.classList.add("d-none");
        reviewsBreakdownEl?.classList.add("d-none");

        reviewsListEl.innerHTML = `
          <div class="product-review-empty">
            <div class="product-review-empty-icon text-danger">!</div>
            <div>
              <h3 class="h6 mb-1">Unable to load reviews</h3>
              <p class="mb-0 text-danger">${escapeHtml(err?.message || "Unable to load reviews.")}</p>
            </div>
          </div>
        `;
      }
    }

    // Public hook for manual refresh
    window.ProductReviews = window.ProductReviews || {};
    window.ProductReviews.reload = loadReviews;

    // Event-driven refresh after review submission
    window.addEventListener("reviews:refresh", (event) => {
      const refreshedProductId = Number(event?.detail?.productId ?? 0);

      if (!refreshedProductId || refreshedProductId === productId) {
        loadReviews();
      }
    });

    loadReviews();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProductReviews);
  } else {
    initProductReviews();
  }
})();