// products/static/products/product_detail.js
document.addEventListener("DOMContentLoaded", () => {
  const minus = document.getElementById("qtyMinus");
  const plus = document.getElementById("qtyPlus");
  const qtyInput = document.getElementById("qtyInput");
  const btn = document.getElementById("addToCartBtn");
  const msg = document.getElementById("productDetailMsg");

  const unitPriceEl = document.getElementById("unitPriceLabel");
  const wholesaleNoticeEl = document.getElementById("wholesaleNotice");

  const surplusNoticeEl = document.getElementById("surplusNotice");
  const compareAtEl = document.getElementById("compareAtPrice");
  const surplusPercentPillEl = document.getElementById("surplusPercentPill");

  // Base price (normal) + surplus price (discounted)
  const baseUnitPrice = Number(btn?.dataset.basePrice ?? "0");
  const surplusActive = (btn?.dataset.surplusActive ?? "0") === "1";
  const surplusUnitPrice = Number(btn?.dataset.surplusPrice ?? "0");
  const surplusPercent = Number(btn?.dataset.surplusPercent ?? "0");
  const surplusNote = (btn?.dataset.surplusNote ?? "").trim();

  // Values injected from template via data-*
  const stockQty = Number(btn?.dataset.stockQty ?? "0");

  const isOutOfStock = !Number.isFinite(stockQty) || stockQty <= 0;

  function clampQty(v) {
    const n = Number(String(v ?? "").trim());
    if (!Number.isFinite(n) || n < 1) return 1;
    return Math.floor(n);
  }

  function setMsg(text, variant = "success") {
    if (!msg) return;
    msg.innerHTML = `<div class="alert alert-${variant} py-2 mb-0">${text}</div>`;
  }

  function setLoading(isLoading) {
    if (!btn) return;

    // Never enable if out of stock
    btn.disabled = isLoading || isOutOfStock;

    if (isLoading) {
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Adding…`;
    } else if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
      delete btn.dataset.originalHtml;
    }
  }

  // ---------- Wholesale helpers ----------
  function getWholesaleTiers() {
    const el = document.getElementById("wholesaleTiersJson");
    if (!el) return [];
    try {
      // [{"min_quantity": 5, "unit_price": "2.50"}, ...]
      return JSON.parse(el.textContent) || [];
    } catch {
      return [];
    }
  }

  const wholesaleTiers = getWholesaleTiers()
    .map((t) => ({
      min: Number(t.min_quantity),
      price: Number(t.unit_price),
    }))
    .filter((t) => Number.isFinite(t.min) && Number.isFinite(t.price))
    .sort((a, b) => a.min - b.min);

  function effectiveUnitPriceForQty(qty) {
    let best = null;
    for (const t of wholesaleTiers) {
      if (qty >= t.min) best = t;
    }
    return best ? best.price : baseUnitPrice;
  }

  function renderUnitPrice() {
    if (!unitPriceEl) return;

    const qty = clampQty(qtyInput?.value ?? 1);

    // Tier-aware unit price
    const tierPrice = effectiveUnitPriceForQty(qty);
    const wholesaleActive = tierPrice !== baseUnitPrice;

    // Decide which price is actually applied to the unit label:
    // 1) wholesale tier (if applicable)
    // 2) else surplus discounted (if active)
    // 3) else base price
    let appliedPrice = baseUnitPrice;
    let appliedMode = "none"; // "none" | "surplus" | "wholesale"

    if (wholesaleActive) {
      appliedPrice = tierPrice;
      appliedMode = "wholesale";
    } else if (
      surplusActive &&
      Number.isFinite(surplusUnitPrice) &&
      surplusUnitPrice > 0
    ) {
      appliedPrice = surplusUnitPrice;
      appliedMode = "surplus";
    }

    unitPriceEl.textContent = `£${appliedPrice.toFixed(2)}`;

    // Compare-at price + percent pill for surplus mode only
    if (compareAtEl && surplusPercentPillEl) {
      if (appliedMode === "surplus") {
        compareAtEl.textContent = `£${baseUnitPrice.toFixed(2)}`;
        setElVisible(compareAtEl, true);

        if (Number.isFinite(surplusPercent) && surplusPercent > 0) {
          surplusPercentPillEl.textContent = `${surplusPercent}% off`;
          setElVisible(surplusPercentPillEl, true);
        } else {
          setElVisible(surplusPercentPillEl, false);
        }
      } else {
        setElVisible(compareAtEl, false);
        setElVisible(surplusPercentPillEl, false);
      }
    }

    // Render the surplus notice block
    renderSurplusNotice({ mode: appliedMode, wholesaleActive });
  }

  function moneyGBP(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "£0.00";
    return `£${n.toFixed(2)}`;
  }

  function renderTierListHtml(qty) {
    const rows = wholesaleTiers
      .map((t) => {
        const active = qty >= t.min;
        return `
          <li class="list-group-item d-flex justify-content-between align-items-center ${
            active ? "fw-semibold" : ""
          }">
            <span>${t.min}+ units</span>
            <span>${moneyGBP(t.price)}</span>
          </li>
        `;
      })
      .join("");

    return `
      <div class="collapse mt-2" id="wholesaleTierList">
        <div class="card card-body p-2">
          <div class="small text-muted mb-1">Wholesale tiers</div>
          <ul class="list-group list-group-flush">
            ${rows}
          </ul>
        </div>
      </div>
    `;
  }

  function renderWholesaleNotice() {
    if (!wholesaleNoticeEl) return;

    // No tiers -> nothing to show
    if (!wholesaleTiers.length) {
      wholesaleNoticeEl.innerHTML = "";
      return;
    }

    const qty = clampQty(qtyInput?.value ?? 1);

    // Find current tier (best applicable)
    let currentTier = null;
    for (const t of wholesaleTiers) {
      if (qty >= t.min) currentTier = t;
    }

    // Find next tier (first tier above qty)
    const nextTier = wholesaleTiers.find((t) => qty < t.min) || null;

    // Wholesale active
    if (currentTier) {
      const savingPerUnit = baseUnitPrice - currentTier.price;
      const savingText =
        savingPerUnit > 0 ? `Save ${moneyGBP(savingPerUnit)} per unit` : "";

      wholesaleNoticeEl.innerHTML = `
        <div class="alert alert-success d-flex align-items-start gap-2 py-2 mb-0"
             role="status"
             style="border-left: 6px solid rgba(25,135,84,.9);">
          <div class="flex-grow-1">
            <div class="fw-semibold">Wholesale price active!</div>
            <div class="small">
              You’re paying <span class="fw-semibold">${moneyGBP(
                currentTier.price,
              )}</span> per unit.
              ${
                savingText
                  ? `<span class="ms-1 text-success-emphasis">${savingText}</span>`
                  : ``
              }
            </div>
            ${
              nextTier
                ? `<div class="small mt-1">
                     Next tier at <span class="fw-semibold">${nextTier.min}+</span>:
                     <span class="fw-semibold">${moneyGBP(
                       nextTier.price,
                     )}</span> per unit.
                   </div>`
                : `<div class="small mt-1">You’ve unlocked the best available tier!</div>`
            }
          </div>

          <button class="btn btn-sm btn-outline-success" type="button"
                  data-bs-toggle="collapse" data-bs-target="#wholesaleTierList"
                  aria-expanded="false" aria-controls="wholesaleTierList">
            View tiers
          </button>
        </div>

        ${renderTierListHtml(qty)}
      `;
      return;
    }

    // Not yet wholesale -> show next tier goal (use first tier)
    const firstTier = wholesaleTiers[0];
    const remaining = Math.max(0, firstTier.min - qty);

    wholesaleNoticeEl.innerHTML = `
      <div class="alert alert-warning d-flex align-items-start gap-2 py-2 mb-0"
           role="status"
           style="border-left: 6px solid rgba(255,193,7,.95);">
        <div class="flex-grow-1">
          <div class="fw-semibold">Wholesale pricing available!</div>
          <div class="small">
            Buy <span class="fw-semibold">${firstTier.min}+</span> to pay
            <span class="fw-semibold">${moneyGBP(firstTier.price)}</span> per unit.
          </div>
          <div class="small mt-1">
            Add <span class="fw-semibold">${remaining}</span> more to unlock this price.
          </div>
        </div>

        <button class="btn btn-sm btn-outline-warning" type="button"
                data-bs-toggle="collapse" data-bs-target="#wholesaleTierList"
                aria-expanded="false" aria-controls="wholesaleTierList">
          View tiers
        </button>
      </div>

      ${renderTierListHtml(qty)}
    `;
  }
  function setElVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function renderSurplusNotice({ mode, wholesaleActive }) {
    // mode: "none" | "surplus" | "wholesale"
    if (!surplusNoticeEl) return;

    // Default: clear
    surplusNoticeEl.innerHTML = "";

    if (!surplusActive) return;

    // If wholesale is active, we still show surplus badge (optional),
    // but we must be honest: wholesale pricing is being applied instead.
    if (wholesaleActive) {
      surplusNoticeEl.innerHTML = `
        <div class="alert alert-info py-2 mb-0" role="status"
             style="border-left: 6px solid rgba(13,110,253,.85);">
          <div class="fw-semibold">Surplus reduction</div>
          <div class="small">
            This item is marked for surplus reduction, but wholesale pricing is currently applied based on quantity.
          </div>
        </div>
      `;
      return;
    }

    // Surplus active (no wholesale tier applied)
    const defaultLine = "Discount applied to clear excess stock.";
    const noteLine =
      surplusNote && surplusNote.toLowerCase() !== "none" ? surplusNote : "";

    surplusNoticeEl.innerHTML = `
      <div class="alert alert-danger py-2 mb-0" role="status"
           style="border-left: 6px solid rgba(220,53,69,.9);">
        <div class="fw-semibold">Surplus reduction</div>
        <div class="small">${defaultLine}</div>
        ${noteLine ? `<div class="small mt-1">${noteLine}</div>` : ""}
      </div>
    `;
  }

  function onQtyChanged() {
    renderUnitPrice();
    renderWholesaleNotice();
  }

  // ---------- Guards ----------
  if (isOutOfStock) {
    setMsg("This product is currently out of stock.", "warning");
    if (btn) btn.disabled = true;
    if (minus) minus.disabled = true;
    if (plus) plus.disabled = true;
    if (qtyInput) qtyInput.disabled = true;
    onQtyChanged();
    return;
  }

  // ---------- Qty events ----------
  minus?.addEventListener("click", () => {
    qtyInput.value = String(clampQty(qtyInput.value) - 1);
    onQtyChanged();
  });

  plus?.addEventListener("click", () => {
    qtyInput.value = String(clampQty(qtyInput.value) + 1);
    onQtyChanged();
  });

  // Live update while typing
  qtyInput?.addEventListener("input", () => {
    qtyInput.value = String(clampQty(qtyInput.value));
    onQtyChanged();
  });

  // Initial render
  onQtyChanged();

  // ---------- Add to cart ----------
  btn?.addEventListener("click", async () => {
    const productId = Number(btn.dataset.productId);
    const quantity = clampQty(qtyInput.value);

    if (!Number.isInteger(productId) || productId <= 0) {
      setMsg("Invalid product id.", "danger");
      return;
    }

    if (!window.CartAPI?.addToCart) {
      setMsg(
        "CartAPI not found. Check base.html loads static 'carts/cart.js' as type=module.",
        "danger",
      );
      return;
    }

    const tierPrice = effectiveUnitPriceForQty(quantity);
    const wholesaleActive = tierPrice !== baseUnitPrice;

    const unitPrice = wholesaleActive
      ? tierPrice
      : surplusActive &&
          Number.isFinite(surplusUnitPrice) &&
          surplusUnitPrice > 0
        ? surplusUnitPrice
        : baseUnitPrice;

    setLoading(true);

    try {
      await window.CartAPI.addToCart({
        productId,
        quantity,
        unitPrice,
      });

      window.CartAPI?.showToast?.(`Added to cart (qty: ${quantity}).`, {
        title: "Cart",
        variant: "success",
        delay: 2000,
      });

      setMsg(`Added to cart (qty: ${quantity}).`, "success");
    } catch (e) {
      const text = e?.message ? e.message : String(e);
      setMsg(`Add to cart failed: ${text}`, "danger");

      window.CartAPI?.showToast?.(`Add to cart failed: ${text}`, {
        title: "Cart",
        variant: "danger",
        delay: 4000,
      });
    } finally {
      setLoading(false);
    }
  });
});
