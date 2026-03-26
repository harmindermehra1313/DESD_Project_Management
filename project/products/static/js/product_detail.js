document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("productDetailPage");
  if (!root) return;

  const productId = Number(root.dataset.productId ?? "0");

  const loadingEl = document.getElementById("productDetailLoading");
  const contentEl = document.getElementById("productDetailContent");
  const msg = document.getElementById("productDetailMsg");

  const minus = document.getElementById("qtyMinus");
  const plus = document.getElementById("qtyPlus");
  const qtyInput = document.getElementById("qtyInput");
  const btn = document.getElementById("addToCartBtn");

  const productImage = document.getElementById("productImage");
  const productName = document.getElementById("productName");
  const productUnit = document.getElementById("productUnit");
  const productCategory = document.getElementById("productCategory");
  const productProducer = document.getElementById("productProducer");
  const availabilityBadge = document.getElementById("availabilityBadge");
  const stockText = document.getElementById("stockText");
  const productDescription = document.getElementById("productDescription");
  const allergensWrap = document.getElementById("allergensWrap");
  const storageGuidance = document.getElementById("storageGuidance");
  const farmOrigin = document.getElementById("farmOrigin");
  const organicCertification = document.getElementById("organicCertification");
  const unitPriceEl = document.getElementById("unitPriceLabel");
  const compareAtEl = document.getElementById("compareAtPrice");
  const surplusPercentPillEl = document.getElementById("surplusPercentPill");
  const surplusNoticeEl = document.getElementById("surplusNotice");
  const wholesaleNoticeEl = document.getElementById("wholesaleNotice");
  const unitLabel = document.getElementById("unitLabel");

  let productData = null;
  let wholesaleTiers = [];

  function moneyGBP(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `£${n.toFixed(2)}` : "£0.00";
  }

  function clampQty(value) {
    const n = Number(String(value ?? "").trim());
    if (!Number.isFinite(n) || n < 1) return 1;
    return Math.floor(n);
  }

  function setMsg(text, variant = "danger") {
    if (!msg) return;
    msg.innerHTML = `<div class="pd-message pd-message--${variant}" role="alert">${text}</div>`;
  }

  function clearMsg() {
    if (!msg) return;
    msg.innerHTML = "";
  }

  function setElVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function getTypedQty() {
    const raw = String(qtyInput?.value ?? "").trim();
    if (raw === "") return null;

    const n = Number(raw);
    if (!Number.isFinite(n)) return null;

    return Math.floor(n);
  }

  function normalizeQtyInput() {
    const quantity = clampQty(qtyInput?.value ?? 1);
    if (qtyInput) {
      qtyInput.value = String(quantity);
    }
    return quantity;
  }

  function getCurrentTierPrice(qty) {
    let best = null;

    for (const tier of wholesaleTiers) {
      if (qty >= tier.min) {
        best = tier;
      }
    }

    return best ? best.price : Number(productData?.effective_price);
  }

  function renderWholesaleNotice(qty) {
    if (!wholesaleNoticeEl || !productData) return;

    if (!wholesaleTiers.length) {
      wholesaleNoticeEl.innerHTML = "";
      return;
    }

    let currentTier = null;
    for (const tier of wholesaleTiers) {
      if (qty >= tier.min) {
        currentTier = tier;
      }
    }

    const nextTier = wholesaleTiers.find((tier) => qty < tier.min) || null;
    const effectiveBasePrice = Number(productData.effective_price);
    const stock = Number(productData.remaining_quantity ?? 0);

    if (currentTier) {
      const savingPerUnit = effectiveBasePrice - currentTier.price;

      wholesaleNoticeEl.innerHTML = `
      <div class="alert alert-warning py-2 mb-0 text-dark" role="status">
        <div class="fw-semibold">Wholesale price active</div>
        <div>
          You’re paying <strong>${moneyGBP(currentTier.price)}</strong> per unit.
          ${savingPerUnit > 0 ? `<span class="ms-1">Save ${moneyGBP(savingPerUnit)} per unit.</span>` : ""}
        </div>
        ${
          nextTier
            ? `<div class="small mt-1">Next tier at ${nextTier.min}+ units: ${moneyGBP(nextTier.price)} per unit.</div>`
            : `<div class="small mt-1">Best available tier unlocked.</div>`
        }
      </div>
    `;
      return;
    }

    const firstTier = wholesaleTiers[0];
    const reachable = stock >= firstTier.min;

    wholesaleNoticeEl.innerHTML = reachable
      ? `
      <div class="alert alert-warning py-2 mb-0 text-dark" role="status">
        <div class="fw-semibold">Wholesale pricing available</div>
        <div>Buy ${firstTier.min}+ to pay ${moneyGBP(firstTier.price)} per unit.</div>
        <div class="small mt-1">Increase quantity to unlock this price.</div>
      </div>
    `
      : `
      <div class="alert alert-warning py-2 mb-0 text-dark" role="status">
        <div class="fw-semibold">Wholesale tier: ${firstTier.min}+ units at ${moneyGBP(firstTier.price)}</div>
        <div class="small mt-1">Not currently reachable with available stock.</div>
      </div>
    `;
  }

  function renderSurplusNotice(wholesaleActive) {
    if (!surplusNoticeEl || !productData) return;

    surplusNoticeEl.innerHTML = "";

    if (!productData.surplus_active) {
      return;
    }

    if (wholesaleActive) {
      surplusNoticeEl.innerHTML = `
      <div class="alert alert-danger py-2 mb-0" role="status">
        <div class="fw-semibold">Surplus reduction</div>
        <div class="small">This item has a surplus reduction, but wholesale pricing is currently applied.</div>
      </div>
    `;
      return;
    }

    surplusNoticeEl.innerHTML = `
    <div class="alert alert-danger py-2 mb-0" role="status">
      <div class="fw-semibold">Surplus reduction</div>
      <div class="small">Discount applied to help clear excess stock.</div>
    </div>
  `;
  }

  function renderPrice(qtyOverride = null) {
    if (!productData) return;

    const qty =
      Number.isFinite(qtyOverride) && qtyOverride >= 1
        ? Math.floor(qtyOverride)
        : normalizeQtyInput();

    const effectivePrice = Number(productData.effective_price);
    const basePrice = Number(productData.price);
    const tierPrice = getCurrentTierPrice(qty);
    const wholesaleActive = tierPrice !== effectivePrice;
    const appliedPrice = wholesaleActive ? tierPrice : effectivePrice;

    unitPriceEl.textContent = moneyGBP(appliedPrice);

    if (wholesaleActive) {
      compareAtEl.textContent = moneyGBP(effectivePrice);
      setElVisible(compareAtEl, true);

      const saving = effectivePrice - appliedPrice;

      if (saving > 0) {
        surplusPercentPillEl.className = "badge rounded-pill bg-danger";
        surplusPercentPillEl.textContent = `Save ${moneyGBP(saving)}`;
      } else {
        surplusPercentPillEl.className =
          "badge rounded-pill bg-warning text-dark";
        surplusPercentPillEl.textContent = "Wholesale";
      }

      setElVisible(surplusPercentPillEl, true);
    } else if (productData.surplus_active && basePrice > effectivePrice) {
      compareAtEl.textContent = moneyGBP(basePrice);
      setElVisible(compareAtEl, true);

      if (productData.surplus_discount_percentage) {
        surplusPercentPillEl.className = "badge rounded-pill bg-danger";
        surplusPercentPillEl.textContent = `${productData.surplus_discount_percentage}% off`;
        setElVisible(surplusPercentPillEl, true);
      } else {
        setElVisible(surplusPercentPillEl, false);
      }
    } else {
      setElVisible(compareAtEl, false);
      setElVisible(surplusPercentPillEl, false);
    }

    renderSurplusNotice(wholesaleActive);
    renderWholesaleNotice(qty);
  }

  function renderStock() {
    if (!productData) return;

    const purchasable = Boolean(productData.is_purchasable);
    const badgeLabel = productData.availability_label || "Unknown";
    const buttonLabel =
      productData.add_to_cart_button_label ||
      (purchasable ? "Add to cart" : "Unavailable");
    const stock = Number(productData.remaining_quantity ?? 0);

    availabilityBadge.className =
      purchasable && stock > 0
        ? "badge rounded-pill text-bg-success"
        : "badge rounded-pill text-bg-secondary";

    availabilityBadge.textContent = badgeLabel;

    stockText.className = "product-stock-text small";

    if (purchasable && stock > 0) {
      if (stock <= 5) {
        stockText.classList.add("is-low");
      }
      stockText.textContent = `${stock} left`;
    } else {
      stockText.textContent = "Currently unavailable";
    }

    btn.disabled = !purchasable;
    qtyInput.disabled = !purchasable;
    minus.disabled = !purchasable;
    plus.disabled = !purchasable;

    btn.classList.add("btn-primary");
    btn.innerHTML = purchasable
      ? `<i class="bi bi-cart-plus me-1"></i>${buttonLabel}`
      : buttonLabel;
  }

  function renderAllergens(allergens) {
    allergensWrap.innerHTML = "";

    if (Array.isArray(allergens) && allergens.length) {
      for (const item of allergens) {
        const span = document.createElement("span");
        span.className = "badge rounded-pill bg-warning text-dark";
        span.textContent = item.allergen?.name || "Unknown";
        allergensWrap.appendChild(span);
      }
      return;
    }

    allergensWrap.innerHTML = `<div class="product-meta-value small">No known allergens.</div>`;
  }
  function renderProduct(data) {
    productData = data;
    wholesaleTiers = (data.wholesale_prices || [])
      .map((tier) => ({
        min: Number(tier.min_quantity),
        price: Number(tier.unit_price),
      }))
      .filter(
        (tier) => Number.isFinite(tier.min) && Number.isFinite(tier.price),
      )
      .sort((a, b) => a.min - b.min);

    productName.textContent = data.name || "";

    productUnit.className = "badge rounded-pill text-bg-primary";
    productUnit.textContent = data.unit || "";

    unitLabel.textContent = data.unit || "";

    productCategory.className = "badge rounded-pill text-bg-secondary";
    productCategory.textContent = data.category?.name || "Uncategorized";

    productProducer.textContent =
      data.producer?.farm_name ||
      data.producer?.business_name ||
      data.producer?.name ||
      "Unknown producer";
    productDescription.textContent =
      data.description || "No description available.";
    storageGuidance.textContent = data.storage_guidance || "—";
    farmOrigin.textContent = data.farm_origin || "—";

    const organicStatus = data.organic_certification_status;
    if (organicStatus === "CERTIFIED") {
      organicCertification.innerHTML =
        '<span class="badge rounded-pill bg-success">Certified organic</span>';
    } else if (organicStatus) {
      organicCertification.innerHTML = `<span class="badge rounded-pill text-bg-secondary">${organicStatus.replaceAll("_", " ")}</span>`;
    } else {
      organicCertification.textContent = "—";
    }

    const imageUrl = data.image || productImage.src;
    productImage.src = imageUrl;
    productImage.alt = data.name || "Product image";

    renderAllergens(data.allergens);
    renderStock();
    renderPrice();

    loadingEl.classList.add("d-none");
    contentEl.classList.remove("d-none");
  }

  async function loadProduct() {
    if (!Number.isInteger(productId) || productId <= 0) {
      if (loadingEl) {
        loadingEl.classList.add("d-none");
      }
      setMsg("Invalid product id.");
      return;
    }

    try {
      const response = await fetch(`/api/products/${productId}/`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error(`Failed to load product (${response.status})`);
      }

      const data = await response.json();
      clearMsg();
      renderProduct(data);
    } catch (err) {
      if (loadingEl) {
        loadingEl.classList.add("d-none");
      }
      setMsg(err?.message || "Failed to load product.");
    }
  }

  minus?.addEventListener("click", () => {
    const qty = normalizeQtyInput();
    qtyInput.value = String(Math.max(1, qty - 1));
    renderPrice();
  });

  plus?.addEventListener("click", () => {
    const qty = normalizeQtyInput();
    qtyInput.value = String(qty + 1);
    renderPrice();
  });

  qtyInput?.addEventListener("input", () => {
    const typedQty = getTypedQty();
    if (typedQty !== null && typedQty >= 1) {
      renderPrice(typedQty);
    }
  });

  qtyInput?.addEventListener("blur", () => {
    normalizeQtyInput();
    renderPrice();
  });

  btn?.addEventListener("click", async () => {
    if (!productData?.is_purchasable) {
      setMsg(
        productData?.stock_message ||
          "This product is not currently available.",
        "warning",
      );
      return;
    }

    if (!productData?.active_inventory_id) {
      setMsg("This product cannot be added to cart right now.", "warning");
      return;
    }

    if (!window.CartAPI?.addToCart) {
      setMsg("CartAPI not found.", "danger");
      return;
    }

    const quantity = normalizeQtyInput();

    try {
      await window.CartAPI.addToCart({
        inventoryId: Number(productData.active_inventory_id),
        quantity,
      });

      if (typeof window.CartAPI?.showToast === "function") {
        window.CartAPI.showToast("Added to cart.", {
          title: "Cart",
          variant: "success",
          delay: 1500,
        });
      } else {
        setMsg("Added to cart.", "success");
      }
    } catch (err) {
      const errorText = `Add to cart failed: ${err?.message || String(err)}`;

      if (typeof window.CartAPI?.showToast === "function") {
        window.CartAPI.showToast(errorText, {
          title: "Cart",
          variant: "danger",
          delay: 2500,
        });
      } else {
        setMsg(errorText, "danger");
      }
    }
  });

  loadProduct();
});
