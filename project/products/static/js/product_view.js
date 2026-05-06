document.addEventListener("DOMContentLoaded", () => {
  const productsDataEl = document.getElementById("productsData");

  if (!productsDataEl) {
    return;
  }

  const products = JSON.parse(productsDataEl.textContent || "[]");

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatPrice(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : "0.00";
  }

  function formatDate(value) {
    if (!value) {
      return "";
    }

    const date = new Date(`${value}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(date);
  }

  function truncateText(value, maxLength = 72) {
    const text = String(value || "").trim();

    if (!text) {
      return "No description available.";
    }

    if (text.length <= maxLength) {
      return text;
    }

    return `${text.slice(0, maxLength).trim()}...`;
  }

  function buildBadge(text, modifierClass) {
    return `
      <span class="product-card-badge ${modifierClass}">
        ${escapeHTML(text)}
      </span>
    `;
  }

  function buildBadges(product) {
    const badges = [];

    if (product.is_disabled) {
      badges.push(
        buildBadge(
          product.disabled_reason || "Unavailable",
          "product-card-badge--muted",
        ),
      );

      return badges.join("");
    }

    badges.push(buildBadge("Available", "product-card-badge--success"));

    if (product.surplus_active) {
      badges.push(buildBadge("Surplus", "product-card-badge--danger"));
    }

    if (product.wholesale_active) {
      badges.push(buildBadge("Wholesale", "product-card-badge--warning"));
    }

    if (product.low_stock) {
      badges.push(buildBadge("Low stock", "product-card-badge--danger"));
    }

    if (product.organic) {
      badges.push(buildBadge("Organic", "product-card-badge--soft"));
    }

    return badges.join("");
  }

  function buildImageHTML(product) {
    if (!product.image) {
      return `
        <div class="product-card-image-placeholder">
          No image
        </div>
      `;
    }

    return `
      <img
        src="${escapeHTML(product.image)}"
        class="product-card-image"
        alt="${escapeHTML(product.name)}"
        loading="lazy"
      >
    `;
  }

  function buildPriceHTML(product) {
    if (product.has_discount) {
      return `
        <div class="product-card-price-row">
          <span class="product-card-price">£${formatPrice(product.price)}</span>
          <span class="product-card-price-compare">£${formatPrice(product.original_price)}</span>
          <span class="product-card-discount">${escapeHTML(product.discount_percent)}% off</span>
        </div>
      `;
    }

    return `
      <div class="product-card-price-row">
        <span class="product-card-price">£${formatPrice(product.price)}</span>
      </div>
    `;
  }

  function buildStockHTML(product) {
    if (product.is_disabled) {
      return `
        <div class="product-card-meta-row">
          <span class="product-card-meta-label">Status</span>
          <span class="product-card-meta-value">
            ${escapeHTML(product.disabled_reason || "Unavailable")}
          </span>
        </div>
      `;
    }

    const expiryText = product.expiry
      ? `Expires ${escapeHTML(formatDate(product.expiry))}`
      : "Expiry unavailable";

    return `
      <div class="product-card-meta-row">
        <span class="product-card-meta-label">Stock</span>
        <span class="product-card-meta-value">
          ${escapeHTML(product.stock)} left
        </span>
      </div>

      <div class="product-card-meta-row">
        <span class="product-card-meta-label">Expiry</span>
        <span class="product-card-meta-value">
          ${expiryText}
        </span>
      </div>
    `;
  }

  function buildAllergensHTML(product) {
    const allergens = Array.isArray(product.allergens)
      ? product.allergens.filter(Boolean)
      : [];

    const allergenText = allergens.length
      ? allergens.join(", ")
      : "No listed allergens";

    return `
    <div class="product-card-meta-row">
      <span class="product-card-meta-label">Allergens</span>
      <span class="product-card-meta-value">
        ${escapeHTML(allergenText)}
      </span>
    </div>
  `;
  }

  function buildActionHTML(product) {
    if (product.is_disabled) {
      return `
      <button
        class="btn btn-primary product-action-btn w-100 mt-auto"
        disabled
      >
        ${escapeHTML(product.disabled_reason || "Unavailable")}
      </button>
    `;
    }

    return `
    <a
      href="/products/${escapeHTML(product.id)}/"
      class="btn btn-primary product-action-btn w-100 mt-auto"
    >
      View details
    </a>
  `;
  }

  function renderProducts(list) {
    const grid = document.getElementById("productGrid");

    if (!grid) {
      return;
    }

    grid.innerHTML = "";

    if (!list.length) {
      grid.innerHTML = `
        <div class="product-empty-state">
          <h2 class="h5 mb-2">No products found</h2>
          <p class="mb-0">
            Try changing the search, category, producer, allergen, or price filters.
          </p>
        </div>
      `;
      return;
    }

    list.forEach((product) => {
      const cardClass = product.is_disabled
        ? "product-card product-card--disabled"
        : "product-card";

      grid.innerHTML += `
        <article class="${cardClass}">

          <div class="product-card-image-wrap">
            ${buildImageHTML(product)}
          </div>

          <div class="product-card-body">

            <div class="product-card-badges">
              ${buildBadges(product)}
            </div>

            <h2 class="product-card-title">
              ${escapeHTML(product.name)}
            </h2>

            <p class="product-card-producer">
              Sold by <strong>${escapeHTML(product.producer)}</strong>
            </p>

            <p class="product-card-description">
              ${escapeHTML(truncateText(product.description))}
            </p>

            <div class="product-card-meta">
              <div class="product-card-meta-row">
                <span class="product-card-meta-label">Category</span>
                <span class="product-card-meta-value">
                  ${escapeHTML(product.category)}
                </span>
              </div>

              ${buildStockHTML(product)}
${buildAllergensHTML(product)}
            </div>

            <div class="product-card-footer">
              ${buildPriceHTML(product)}
              ${buildActionHTML(product)}
            </div>

          </div>
        </article>
      `;
    });
  }

  renderProducts(products);
});