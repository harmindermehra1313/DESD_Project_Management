// added food miles - joe
const M = window.ProductDetailMessages;
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
  const foodMiles = document.getElementById("foodMiles");
  const organicCertification = document.getElementById("organicCertification");
  const unitPriceEl = document.getElementById("unitPriceLabel");
  const compareAtEl = document.getElementById("compareAtPrice");
  const surplusPercentPillEl = document.getElementById("surplusPercentPill");
  const surplusNoticeEl = document.getElementById("surplusNotice");
  const wholesaleNoticeEl = document.getElementById("wholesaleNotice");
  const unitLabel = document.getElementById("unitLabel");
  const expiryInfoRow = document.getElementById("expiryInfoRow");
  const expiryTypeLabel = document.getElementById("expiryTypeLabel");
  const expiryValue = document.getElementById("expiryValue");

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

  function parseMiles(value) {
    if (value === null || value === undefined || value === "") {
      return NaN;
    }

    const n = Number(value);
    return Number.isFinite(n) ? n : NaN;
  }

  function setMsg(text, variant = "danger") {
    if (!msg) return;
    msg.innerHTML = `<div class="pd-message pd-message--${variant}" role="alert">${text}</div>`;
  }

  function clearMsg() {
    if (!msg) return;
    msg.innerHTML = "";
  }
  function formatDate(value) {
    if (!value) return "—";

    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;

    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(date);
  }

  function buildUnavailableMessage() {
    if (!productData) {
      return M.unavailable;
    }

    if (productData.is_expired) {
      const label = M.getExpiryLabel(productData);
      const dateText = productData.expiry_date
        ? formatDate(productData.expiry_date)
        : null;

      return dateText
        ? `This item has expired.`
        : "This item has expired and cannot be added to your cart.";
    }

    return (
      productData.stock_message ||
      productData.add_to_cart_button_label ||
      M.unavailable
    );
  }

  function renderExpiry() {
    if (!productData || !expiryInfoRow || !expiryTypeLabel || !expiryValue)
      return;

    const hasExpiry = Boolean(
      productData.expiry_date || productData.expiry_type_label,
    );

    setElVisible(expiryInfoRow, hasExpiry);

    if (!hasExpiry) {
      expiryTypeLabel.textContent = M.expiryLabel;
      expiryValue.textContent = M.dash;
      expiryValue.className = "product-meta-value";
      return;
    }

    expiryTypeLabel.textContent = M.getExpiryLabel(productData);
    expiryValue.textContent = productData.expiry_date
      ? formatDate(productData.expiry_date)
      : M.dash;

    expiryValue.className = productData.is_expired
      ? "product-meta-value text-danger fw-semibold"
      : "product-meta-value";
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
        <div class="fw-semibold">${M.wholesalePriceActiveTitle}</div>
        <div>
          <strong>${M.payingPerUnit(moneyGBP(currentTier.price))}</strong>
          ${savingPerUnit > 0 ? `<span class="ms-1">${M.savePerUnit(moneyGBP(savingPerUnit))}</span>` : ""}
        </div>
        ${
          nextTier
            ? `<div class="small mt-1">${M.nextTier(nextTier.min, moneyGBP(nextTier.price))}</div>`
            : `<div class="small mt-1">${M.bestAvailableTierUnlocked}</div>`
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
        <div class="fw-semibold">${M.wholesalePricingAvailableTitle}</div>
        <div>${M.wholesaleUnlock(firstTier.min, moneyGBP(firstTier.price))}</div>
        <div class="small mt-1">${M.increaseQuantityHint}</div>
      </div>
    `
      : `
      <div class="alert alert-warning py-2 mb-0 text-dark" role="status">
        <div class="fw-semibold">${M.wholesaleTier(firstTier.min, moneyGBP(firstTier.price))}</div>
        <div class="small mt-1">${M.notCurrentlyReachable}</div>
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
        <div class="fw-semibold">${M.surplusReductionTitle}</div>
        <div class="small">${M.surplusWholesaleAppliedNote}</div>
      </div>
    `;
      return;
    }

    surplusNoticeEl.innerHTML = `
    <div class="alert alert-danger py-2 mb-0" role="status">
      <div class="fw-semibold">${M.surplusReductionTitle}</div>
      <div class="small">${M.surplusDiscountAppliedNote}</div>
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
        surplusPercentPillEl.textContent = M.saveAmount(moneyGBP(saving));
      } else {
        surplusPercentPillEl.className =
          "badge rounded-pill bg-warning text-dark";
        surplusPercentPillEl.textContent = M.wholesaleLabel;
      }

      setElVisible(surplusPercentPillEl, true);
    } else if (productData.surplus_active && basePrice > effectivePrice) {
      compareAtEl.textContent = moneyGBP(basePrice);
      setElVisible(compareAtEl, true);

      if (productData.surplus_discount_percentage) {
        surplusPercentPillEl.className = "badge rounded-pill bg-danger";
        surplusPercentPillEl.textContent = M.percentOff(
          productData.surplus_discount_percentage,
        );
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
    const badgeLabel =
      productData.availability_label ||
      M.getBadgeLabel(productData, purchasable);

    const badgeClass =
      productData.availability_badge_class ||
      (purchasable ? "text-bg-success" : "text-bg-secondary");

    const buttonLabel =
      productData.add_to_cart_button_label ||
      M.getButtonLabel(productData, purchasable);

    availabilityBadge.className = `badge rounded-pill ${badgeClass}`;
    availabilityBadge.textContent = badgeLabel;

    stockText.className = "product-stock-text small";
    stockText.textContent = buildUnavailableMessage();

    if (purchasable) {
      stockText.textContent =
        productData.stock_message ||
        M.getStockText(
          productData,
          Number(productData.remaining_quantity ?? 0),
        );

      if (productData.availability_label === "Low stock") {
        stockText.classList.add("is-low");
      }
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
        span.textContent = item.allergen?.name || M.unknownLabel;
        allergensWrap.appendChild(span);
      }
      return;
    }

    allergensWrap.innerHTML = `<div class="product-meta-value small">${M.noKnownAllergens}</div>`;
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
    productCategory.textContent = data.category?.name || M.uncategorized;

    productProducer.textContent =
      data.producer?.farm_name ||
      data.producer?.business_name ||
      data.producer?.name ||
      M.unknownProducer;
    productDescription.textContent = data.description || M.noDescription;
    storageGuidance.textContent = data.storage_guidance || M.dash;
    farmOrigin.textContent = data.farm_origin || M.dash;

    if (foodMiles) {
      const miles = parseMiles(data.food_miles);
      if (Number.isFinite(miles)) {
        foodMiles.textContent = `${miles.toFixed(2)} miles from farm to your default delivery postcode`;
      } else if (data.food_miles_login_required) {
        foodMiles.textContent = "Log in to see your food miles.";
      } else if (data.customer_postcode) {
        foodMiles.textContent = "Food miles are currently unavailable for this route.";
      } else {
        foodMiles.textContent = "Add a delivery address to view food miles.";
      }
    }

    const organicStatus = data.organic_certification_status;
    if (organicStatus === "CERTIFIED") {
      organicCertification.innerHTML = M.getOrganicStatusMarkup(organicStatus);
    } else if (organicStatus) {
      organicCertification.innerHTML = M.getOrganicStatusMarkup(organicStatus);
    } else {
      organicCertification.textContent = M.dash;
    }

    const imageUrl = data.image || productImage.src;
    productImage.src = imageUrl;
    productImage.alt = M.getImageAlt(data.name);

    renderAllergens(data.allergens);
    renderExpiry();
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
      setMsg(M.invalidProductId);
      return;
    }

    try {
      const response = await fetch(`/api/products/${productId}/`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error(M.loadFailed);
      }

      const data = await response.json();
      clearMsg();
      renderProduct(data);
    } catch (err) {
      if (loadingEl) {
        loadingEl.classList.add("d-none");
      }
      setMsg(M.getLoadError(err));
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
      setMsg(buildUnavailableMessage(), "warning");
      return;
    }

    if (!productData?.active_inventory_id) {
      setMsg(M.missingInventory, "warning");
      return;
    }

    if (!window.CartAPI?.addToCart) {
      setMsg(M.cartUnavailable, "danger");
      return;
    }

    const quantity = normalizeQtyInput();

    try {
      await window.CartAPI.addToCart({
        inventoryId: Number(productData.active_inventory_id),
        quantity,
      });

      if (typeof window.CartAPI?.showToast === "function") {
        window.CartAPI.showToast(M.addedToCart, {
          title: window.CartApiMessages?.cartTitle || "Cart",
          variant: "success",
          delay: 1500,
        });
      } else {
        setMsg(M.addedToCart, "success");
      }
    } catch (err) {
      const friendlyMessage = M.getAddError(err, productData, formatDate,  quantity);

      if (typeof window.CartAPI?.showToast === "function") {
        window.CartAPI.showToast(friendlyMessage, {
          title: window.CartApiMessages?.cartTitle || "Cart",
          variant: "danger",
          delay: 2500,
        });
      } else {
        setMsg(friendlyMessage, "danger");
      }
    }
  });
  function loadRecipeSuggestions(productId) {
    fetch(`/products/product/${productId}/recipes/`)
      .then(res => res.json())
      .then(data => {
        const wrap = document.getElementById("recipeSuggestions");
        if (!wrap) return;

        if (!data.recipes.length) {
          wrap.innerHTML = `<p class="text-muted">No recipes linked yet.</p>`;
          return;
        }

        wrap.innerHTML = data.recipes.map(r => `
          <div class="d-flex align-items-center mb-3">
            <img src="${r.image}" 
                style="width:70px;height:70px;object-fit:cover;border-radius:6px;"
                class="me-3">
            <div>
              <a href="/community/recipes/${r.id}/" class="fw-bold">${r.title}</a><br>
              ${r.season ? `<span class="badge bg-secondary">${r.season}</span>` : ""}
            </div>
          </div>
        `).join("");
      })
      .catch(() => {
        const wrap = document.getElementById("recipeSuggestions");
        if (wrap) wrap.innerHTML = `<p class="text-danger">Failed to load recipes.</p>`;
      });
  }

  loadRecipeSuggestions(productId);
  loadProduct();
});
