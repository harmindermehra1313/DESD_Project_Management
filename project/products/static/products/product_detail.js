// products/static/products/product_detail.js
document.addEventListener("DOMContentLoaded", () => {
  const minus = document.getElementById("qtyMinus");
  const plus = document.getElementById("qtyPlus");
  const qtyInput = document.getElementById("qtyInput");
  const btn = document.getElementById("addToCartBtn");
  const msg = document.getElementById("productDetailMsg");

  const unitPriceEl = document.getElementById("unitPriceLabel");

  // Values injected from template via data-* (no Django {{ }} inside JS file)
  const stockQty = Number(btn?.dataset.stockQty ?? "0");
  const baseUnitPrice = Number(btn?.dataset.basePrice ?? "0");

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
      btn.innerHTML =
        `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Adding…`;
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
    const price = effectiveUnitPriceForQty(qty);
    unitPriceEl.textContent = `£${price.toFixed(2)}`;
  }

  // ---------- Guards ----------
  if (isOutOfStock) {
    setMsg("This product is currently out of stock.", "warning");
    if (btn) btn.disabled = true;
    if (minus) minus.disabled = true;
    if (plus) plus.disabled = true;
    if (qtyInput) qtyInput.disabled = true;
    renderUnitPrice();
    return;
  }

  // ---------- Qty events ----------
  minus?.addEventListener("click", () => {
    qtyInput.value = String(clampQty(qtyInput.value) - 1);
    renderUnitPrice();
  });

  plus?.addEventListener("click", () => {
    qtyInput.value = String(clampQty(qtyInput.value) + 1);
    renderUnitPrice();
  });

  qtyInput?.addEventListener("change", () => {
    qtyInput.value = String(clampQty(qtyInput.value));
    renderUnitPrice();
  });

  // initial render
  renderUnitPrice();

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
        "danger"
      );
      return;
    }

    // Send correct unit price into cart pricing (based on current qty tier)
    const unitPrice = effectiveUnitPriceForQty(quantity);

    setLoading(true);

    try {
      await window.CartAPI.addToCart({
        productId,
        quantity,
        unitPrice, // important: tier-aware unit price
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