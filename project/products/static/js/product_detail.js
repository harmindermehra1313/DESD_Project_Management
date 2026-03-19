document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("productDetailPage");
  const productId = Number(root?.dataset.productId ?? "0");

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
  const stockCount = document.getElementById("stockCount");
  const productDescription = document.getElementById("productDescription");
  const allergensWrap = document.getElementById("allergensWrap");
  const storageGuidance = document.getElementById("storageGuidance");
  const farmOrigin = document.getElementById("farmOrigin");

  const unitPriceEl = document.getElementById("unitPriceLabel");
  const compareAtEl = document.getElementById("compareAtPrice");
  const surplusPercentPillEl = document.getElementById("surplusPercentPill");
  const surplusNoticeEl = document.getElementById("surplusNotice");
  const wholesaleNoticeEl = document.getElementById("wholesaleNotice");
  const unitLabel = document.getElementById("unitLabel");

  let productData = null;
  let wholesaleTiers = [];

  function moneyGBP(v) {
    const n = Number(v);
    return Number.isFinite(n) ? `£${n.toFixed(2)}` : "£0.00";
  }

  function clampQty(v) {
    const n = Number(String(v ?? "").trim());
    if (!Number.isFinite(n) || n < 1) return 1;
    return Math.floor(n);
  }

  function setMsg(text, variant = "danger") {
    if (!msg) return;
    msg.innerHTML = `<div class="alert alert-${variant} py-2 mb-0" role="alert">${text}</div>`;
  }

  function clearMsg() {
    if (msg) msg.innerHTML = "";
  }

  function setElVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function getCurrentTierPrice(qty) {
    let best = null;
    for (const t of wholesaleTiers) {
      if (qty >= t.min) best = t;
    }
    return best ? best.price : Number(productData.effective_price);
  }

  function renderWholesaleNotice(qty) {
    if (!wholesaleNoticeEl) return;

    if (!wholesaleTiers.length) {
      wholesaleNoticeEl.innerHTML = "";
      return;
    }

    let currentTier = null;
    for (const t of wholesaleTiers) {
      if (qty >= t.min) currentTier = t;
    }

    const nextTier = wholesaleTiers.find((t) => qty < t.min) || null;
    const effectiveBasePrice = Number(productData.effective_price);

    if (currentTier) {
      const savingPerUnit = effectiveBasePrice - currentTier.price;

      wholesaleNoticeEl.innerHTML = `
        <div class="alert alert-success py-2 mb-0" role="status">
          <div class="fw-semibold">Wholesale price active</div>
          <div class="small">
            You’re paying <span class="fw-semibold">${moneyGBP(currentTier.price)}</span> per unit.
            ${savingPerUnit > 0 ? `<span class="ms-1">Save ${moneyGBP(savingPerUnit)} per unit.</span>` : ""}
          </div>
          ${nextTier ? `<div class="small mt-1">Next tier at ${nextTier.min}+ units: ${moneyGBP(nextTier.price)} per unit.</div>` : `<div class="small mt-1">Best available tier unlocked.</div>`}
        </div>
      `;
      return;
    }

    const firstTier = wholesaleTiers[0];
    const remaining = Math.max(0, firstTier.min - qty);

    wholesaleNoticeEl.innerHTML = `
      <div class="alert alert-warning py-2 mb-0" role="status">
        <div class="fw-semibold">Wholesale pricing available</div>
        <div class="small">
          Buy ${firstTier.min}+ to pay ${moneyGBP(firstTier.price)} per unit.
        </div>
        <div class="small mt-1">Add ${remaining} more to unlock this price.</div>
      </div>
    `;
  }

  function renderSurplusNotice(wholesaleActive) {
    if (!surplusNoticeEl) return;
    surplusNoticeEl.innerHTML = "";

    if (!productData.surplus_active) return;

    if (wholesaleActive) {
      surplusNoticeEl.innerHTML = `
        <div class="alert alert-info py-2 mb-0" role="status">
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

  function renderPrice() {
    const qty = clampQty(qtyInput?.value ?? 1);

    const baseEffectivePrice = Number(productData.effective_price);
    const rawBasePrice = Number(productData.price);
    const tierPrice = getCurrentTierPrice(qty);
    const wholesaleActive = tierPrice !== baseEffectivePrice;

    let appliedPrice = wholesaleActive ? tierPrice : baseEffectivePrice;

    unitPriceEl.textContent = moneyGBP(appliedPrice);

    if (wholesaleActive) {
      compareAtEl.textContent = moneyGBP(baseEffectivePrice);
      setElVisible(compareAtEl, true);

      const saving = baseEffectivePrice - appliedPrice;
      surplusPercentPillEl.textContent = saving > 0 ? `Save ${moneyGBP(saving)}` : "Wholesale";
      setElVisible(surplusPercentPillEl, true);
    } else if (productData.surplus_active && rawBasePrice > baseEffectivePrice) {
      compareAtEl.textContent = moneyGBP(rawBasePrice);
      setElVisible(compareAtEl, true);

      if (productData.surplus_discount_percentage) {
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
    const stock = Number(productData.remaining_quantity ?? 0);
    const threshold = Number(productData.low_stock_threshold ?? 0);
    const outOfStock = stock <= 0;

    availabilityBadge.className = "badge";
    if (productData.availability_status === "AV") {
      availabilityBadge.classList.add("text-bg-success");
    } else if (productData.availability_status === "OOS") {
      availabilityBadge.classList.add("text-bg-danger");
    } else {
      availabilityBadge.classList.add("text-bg-secondary");
    }
    availabilityBadge.textContent = productData.availability_status;

    if (outOfStock) {
      stockText.className = "text-danger small";
      stockText.textContent = "Out of stock";
    } else if (stock <= threshold) {
      stockText.className = "text-warning small";
      stockText.textContent = `Low stock — only ${stock} left`;
    } else {
      stockText.className = "text-muted small";
      stockText.textContent = "In stock";
    }

    stockCount.textContent = `Stock: ${stock}`;

    btn.disabled = outOfStock || !productData.active_inventory_id;
    qtyInput.disabled = outOfStock;
    minus.disabled = outOfStock;
    plus.disabled = outOfStock;

    if (outOfStock) {
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-secondary");
      btn.innerHTML = "Out of stock";
    }
  }

  function renderProduct(data) {
    productData = data;
    wholesaleTiers = (data.wholesale_prices || [])
      .map((t) => ({
        min: Number(t.min_quantity),
        price: Number(t.unit_price),
      }))
      .filter((t) => Number.isFinite(t.min) && Number.isFinite(t.price))
      .sort((a, b) => a.min - b.min);

    productName.textContent = data.name || "";
    productUnit.textContent = data.unit || "";
    unitLabel.textContent = data.unit || "";
    productCategory.textContent = data.category?.name || "Uncategorized";
    productProducer.textContent = data.producer?.business_name || data.producer?.name || "Unknown producer";
    productDescription.textContent = data.description || "No description available.";
    storageGuidance.textContent = data.storage_guidance || "—";
    farmOrigin.textContent = data.farm_origin || "—";

    const imageUrl = data.image || productImage.src;
    productImage.src = imageUrl;
    productImage.alt = data.name || "Product image";

    allergensWrap.innerHTML = "";
    if (Array.isArray(data.allergens) && data.allergens.length) {
      for (const item of data.allergens) {
        const span = document.createElement("span");
        span.className = "badge bg-warning text-dark";
        span.textContent = item.allergen?.name || "Unknown";
        allergensWrap.appendChild(span);
      }
    } else {
      allergensWrap.innerHTML = `<div class="text-muted small">No known allergens.</div>`;
    }

    renderStock();
    renderPrice();

    loadingEl.classList.add("d-none");
    contentEl.classList.remove("d-none");
  }

  async function loadProduct() {
    if (!Number.isInteger(productId) || productId <= 0) {
      setMsg("Invalid product id.");
      return;
    }

    try {
      const res = await fetch(`/api/products/${productId}/`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });

      if (!res.ok) {
        throw new Error(`Failed to load product (${res.status})`);
      }

      const data = await res.json();
      clearMsg();
      renderProduct(data);
    } catch (err) {
      loadingEl.classList.add("d-none");
      setMsg(err?.message || "Failed to load product.");
    }
  }

  function normalizeQtyInput() {
    const q = clampQty(qtyInput?.value ?? 1);
    qtyInput.value = String(q);
    return q;
  }

  minus?.addEventListener("click", () => {
    const q = normalizeQtyInput();
    qtyInput.value = String(Math.max(1, q - 1));
    renderPrice();
  });

  plus?.addEventListener("click", () => {
    const q = normalizeQtyInput();
    qtyInput.value = String(q + 1);
    renderPrice();
  });

  qtyInput?.addEventListener("input", renderPrice);
  qtyInput?.addEventListener("blur", () => {
    normalizeQtyInput();
    renderPrice();
  });

  btn?.addEventListener("click", async () => {
    if (!productData?.active_inventory_id) {
      setMsg("This product is not currently available.", "warning");
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
      setMsg(`Add to cart failed: ${err?.message || String(err)}`, "danger");
    }
  });

  loadProduct();
});