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

    // Check if the product is disabled (or specifically out of season)
    if (product.is_disabled || (product.is_seasonal && !product.in_season)) {
      let reason = product.disabled_reason || "Unavailable";
      let badgeClass = "product-card-badge--muted";
      
      // Override text and color if it's simply out of season
      if (product.is_seasonal && !product.in_season) {
        reason = "Out of Season";
        badgeClass = "product-card-badge--warning";
      }

      badges.push(buildBadge(reason, badgeClass));
      return badges.join("");
    }

    badges.push(buildBadge("Available", "product-card-badge--success"));

    // Add Seasonal Badge if applicable
    if (product.is_seasonal && product.in_season) {
      badges.push(buildBadge("In Season", "product-card-badge--success"));
    }

    // Add Discount/Surplus badges
    if (product.discount_reason === "Expires soon") {
      badges.push(buildBadge("Expires soon", "product-card-badge--danger"));
    } else if (product.surplus_active) {
      badges.push(buildBadge("Surplus", "product-card-badge--danger"));
<<<<<<< HEAD
    } else if (product.wholesale_active) {
      badges.push(buildBadge("Wholesale", "product-card-badge--warning"));
    } else if (product.low_stock) {
=======
    }

    if (product.wholesale_active) {
      badges.push(buildBadge("Wholesale", "product-card-badge--warning"));
    }

    if (product.low_stock) {
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
      badges.push(buildBadge("Low stock", "product-card-badge--danger"));
    }

    if (product.organic) {
      badges.push(buildBadge("Organic", "product-card-badge--soft"));
    }

<<<<<<< HEAD
    return badges.slice(0, 3).join("");
=======
    return badges.join("");
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
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
    // If the product is disabled but NOT because it's out of season, show the standard disabled reason
    if (product.is_disabled && !(product.is_seasonal && !product.in_season)) {
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

<<<<<<< HEAD
  function buildActionHTML(product) {
  if (product.is_disabled) {
    return `
=======
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
    if (product.is_disabled || (product.is_seasonal && !product.in_season)) {
      let reason = product.disabled_reason || "Unavailable";
      
      if (product.is_seasonal && !product.in_season) {
        reason = "Out of Season";
      }

      return `
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
      <button
        class="btn btn-primary product-action-btn w-100 mt-auto"
        disabled
      >
        ${escapeHTML(product.disabled_reason || "Unavailable")}
      </button>
    `;
<<<<<<< HEAD
  }

  return `
=======
    }

    return `
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
    <a
      href="/products/${escapeHTML(product.id)}/"
      class="btn btn-primary product-action-btn w-100 mt-auto"
    >
      View details
    </a>
  `;
<<<<<<< HEAD
}
=======
  }
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64

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
<<<<<<< HEAD
            Try changing the search, category, producer, or price filters.
=======
            Try changing the search, category, producer, allergen, or price filters.
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
          </p>
        </div>
      `;
      return;
    }

    list.forEach((product) => {
      // Out of season items will get the disabled UI fade applied to the card
      const cardClass = product.is_disabled || (product.is_seasonal && !product.in_season)
        ? "product-card product-card--disabled"
        : "product-card";

      // Build seasonal metadata row if applicable
      let seasonalTextHtml = '';
      if (product.is_seasonal) {
        seasonalTextHtml = `
          <div class="product-card-meta-row">
            <span class="product-card-meta-label">Season</span>
            <span class="product-card-meta-value">
              ${escapeHTML(product.season_text)}
            </span>
          </div>
        `;
      }

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
              
              ${seasonalTextHtml}
              ${buildStockHTML(product)}
<<<<<<< HEAD
=======
${buildAllergensHTML(product)}
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
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
<<<<<<< HEAD
});
=======
});
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
