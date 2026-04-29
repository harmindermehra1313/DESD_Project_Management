document.addEventListener("DOMContentLoaded", () => {
    const products = JSON.parse(document.getElementById("productsData").textContent);
    const showFilters = document.getElementById("showFiltersFlag").textContent.trim() === "true";

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

    

    function buildBadge(text, cssClass) {
        return `<span class="badge ${cssClass} me-1 mb-1">${escapeHTML(text)}</span>`;
    }

    function buildBadges(product) {
        let badges = "";

        if (product.is_disabled) {
            return buildBadge(product.disabled_reason || "Unavailable", "bg-secondary");
        }

        if (product.surplus_active) {
            badges += buildBadge("Surplus active", "bg-warning text-dark");
        }

        if (product.wholesale_active) {
            badges += buildBadge("Wholesale available", "bg-info text-dark");
        }

        if (product.low_stock) {
            badges += buildBadge("Low stock", "bg-danger");
        }

        if (product.organic) {
            badges += buildBadge("Organic", "bg-success");
        }

        if (product.local) {
            badges += buildBadge("Local", "bg-primary");
        }

        if (product.fresh_today) {
            badges += buildBadge("Fresh Today", "bg-light text-dark border");
        }

        return badges;
    }

    function buildPriceHTML(product) {
        if (product.has_discount) {
            return `
                <div class="mb-3">
                    <span class="text-danger fw-bold">£${formatPrice(product.price)}</span>
                    <span class="text-muted text-decoration-line-through ms-2">
                        £${formatPrice(product.original_price)}
                    </span>
                    <span class="badge bg-danger ms-2">
                        -${escapeHTML(product.discount_percent)}%
                    </span>
                </div>
            `;
        }

        return `
            <h5 class="fw-bold mb-3 text-success">
                £${formatPrice(product.price)}
            </h5>
        `;
    }

    function buildActionHTML(product) {
        if (product.is_disabled) {
            return `
                <button class="btn btn-secondary w-100 mt-auto" disabled>
                    ${escapeHTML(product.disabled_reason || "Unavailable")}
                </button>
            `;
        }

        return `
            <a href="/products/${product.id}/"
               class="btn btn-brand-outline w-100 mt-auto">
                More Information
            </a>
        `;
    }

    function buildImageHTML(product) {
        if (!product.image) {
            return `
                <div class="product-img-wrapper d-flex align-items-center justify-content-center">
                    <span class="text-muted small">No image available</span>
                </div>
            `;
        }

        return `
            <img src="${escapeHTML(product.image)}"
                 class="card-img-top"
                 alt="${escapeHTML(product.name)}"
                 loading="lazy">
        `;
    }

    function renderProducts(list) {
        const grid = document.getElementById("productGrid");
        grid.innerHTML = "";

        if (list.length === 0) {
            grid.innerHTML = "<p class='text-muted text-center mt-3'>No products found.</p>";
            return;
        }

        list.forEach(product => {
            const shortDesc = product.description
                ? `${product.description.substring(0, 60)}...`
                : "No description available.";

            const cardClass = product.is_disabled
                ? "card h-100 shadow-sm product-card product-card--disabled"
                : "card h-100 shadow-sm product-card";

            grid.innerHTML += `
                <div class="col">
                    <div class="${cardClass}">

                        <div class="card-header bg-white text-center fw-bold border-0 pt-3">
                            ${escapeHTML(product.name)}
                        </div>

                        ${buildImageHTML(product)}

                        <div class="card-body d-flex flex-column">

                            <div class="mb-2">
                                ${buildBadges(product)}
                            </div>

                            <p class="text-muted small mb-2">
                                By: ${escapeHTML(product.producer)}
                            </p>

                            <p class="card-text small mb-3">
                                ${escapeHTML(shortDesc)}
                            </p>

                            <p class="text-muted small mb-2">
                                Stock: ${escapeHTML(product.stock)}
                                ${product.expiry ? ` · Expires: ${escapeHTML(product.expiry)}` : ""}
                            </p>

                            ${buildPriceHTML(product)}

                            ${buildActionHTML(product)}
                        </div>
                    </div>
                </div>
            `;
        });
    }

    

    

    renderProducts(products);
});