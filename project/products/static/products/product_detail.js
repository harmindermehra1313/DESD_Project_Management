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
    return Math.floor(n); // integer-only
  }

  function setMsg(text, variant = "success", { timeout = 2000 } = {}) {
    if (!msg) return;

    msg.innerHTML = `<div class="alert alert-${variant} py-2 mb-0" role="alert">${text}</div>`;

    // auto-dismiss
    window.clearTimeout(setMsg._t);
    setMsg._t = window.setTimeout(() => {
      if (msg) msg.innerHTML = "";
    }, timeout);
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

  function moneyGBP(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "£0.00";
    return `£${n.toFixed(2)}`;
  }

  function setElVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  // ---------- Surplus notice ----------
  function renderSurplusNotice({ wholesaleActive }) {
    if (!surplusNoticeEl) return;

    surplusNoticeEl.innerHTML = "";
    if (!surplusActive) return;

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

    const defaultLine = "Discount applied to clear excess stock.";
    const noteLine =
      surplusNote && surplusNote.toLowerCase() !== "none" ? surplusNote : "";

    surplusNoticeEl.innerHTML = `
      <div class="alert alert-danger py-2 mb-0" role="status"
           style="border-left: 6px solid rgba(220,53,69,.9);">
        <div class="fw-semibold">Surplus reduction</div>
        ${noteLine ? `<div class="small mt-1">${noteLine}</div>` : ""}
      </div>
    `;
  }

  // ---------- Wholesale notice ----------
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

    if (!wholesaleTiers.length) {
      wholesaleNoticeEl.innerHTML = "";
      return;
    }

    const qty = clampQty(qtyInput?.value ?? 1);

    // Current tier (best applicable)
    let currentTier = null;
    for (const t of wholesaleTiers) {
      if (qty >= t.min) currentTier = t;
    }

    // Next tier
    const nextTier = wholesaleTiers.find((t) => qty < t.min) || null;

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

  // ---------- Price rendering ----------
  function renderUnitPrice() {
    if (!unitPriceEl) return;

    const qty = clampQty(qtyInput?.value ?? 1);

    const tierPrice = effectiveUnitPriceForQty(qty);
    const wholesaleActive = tierPrice !== baseUnitPrice;

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

    renderSurplusNotice({ wholesaleActive });
  }

  function onQtyChanged() {
    renderUnitPrice();
    renderWholesaleNotice();

    // Optional pro UX: disable minus at 1
    if (minus) minus.disabled = clampQty(qtyInput?.value ?? 1) <= 1;
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

  // ---------- Qty events (cart-style: free typing, clamp on commit) ----------
  function normalizeQtyInput() {
    if (!qtyInput) return 1;
    const q = clampQty(qtyInput.value);
    qtyInput.value = String(q);
    return q;
  }

  minus?.addEventListener("click", () => {
    const q = normalizeQtyInput();
    qtyInput.value = String(Math.max(1, q - 1));
    onQtyChanged();
  });

  plus?.addEventListener("click", () => {
    const q = normalizeQtyInput();
    qtyInput.value = String(q + 1);
    onQtyChanged();
  });

  // While typing: don't clamp; just re-render using clampQty for preview
  qtyInput?.addEventListener("input", () => {
    onQtyChanged();
  });

  // Commit: when they finish editing, clamp to int >= 1
  qtyInput?.addEventListener("blur", () => {
    normalizeQtyInput();
    onQtyChanged();
  });

  qtyInput?.addEventListener("change", () => {
    normalizeQtyInput();
    onQtyChanged();
  });

  qtyInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      normalizeQtyInput();
      onQtyChanged();
      qtyInput.blur();
    }
  });

  // Initial render
  onQtyChanged();

  // ---------- Add to cart ----------
  btn?.addEventListener("click", async () => {
  const productId = Number(btn.dataset.productId);
  const quantity = normalizeQtyInput();

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

  setLoading(true);

  try {
    // IMPORTANT: server decides wholesale/surplus unit price.
    // We only send product + quantity.
    await window.CartAPI.addToCart({
      productId,
      quantity,
    });

    // Prefer toast (short), fallback to inline auto-dismiss
    if (typeof window.CartAPI?.showToast === "function") {
      window.CartAPI.showToast("Added to cart.", {
        title: "Cart",
        variant: "success",
        delay: 1500,
      });
    } else {
      setMsg("Added to cart.", "success", { timeout: 1500 });
    }
  } catch (e) {
    const text = e?.message ? e.message : String(e);

    // Errors: show longer so user can read
    if (typeof window.CartAPI?.showToast === "function") {
      window.CartAPI.showToast(`Add to cart failed: ${text}`, {
        title: "Cart",
        variant: "danger",
        delay: 3500,
      });
    } else {
      setMsg(`Add to cart failed: ${text}`, "danger", { timeout: 4000 });
    }
  } finally {
    setLoading(false);
  }
});
});
