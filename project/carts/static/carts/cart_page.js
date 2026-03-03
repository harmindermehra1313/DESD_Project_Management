// carts/static/carts/cart_page.js
document.addEventListener("DOMContentLoaded", () => {
  const cartMsg = document.getElementById("cartMsg");
  const cartItemsEl = document.getElementById("cartItems");
  const cartEmptyEl = document.getElementById("cartEmpty");

  const distinctItemsEl = document.getElementById("distinctItems");
  const totalQtyEl = document.getElementById("totalQty");
  const subtotalEl = document.getElementById("subtotal");
  const totalEl = document.getElementById("total");

  const checkoutBtn = document.getElementById("checkoutBtn");

  const GBP = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  });

  function money(v) {
    const n = Number(v);
    return GBP.format(Number.isFinite(n) ? n : 0);
  }

  function toNum(v, fallback = 0) {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  function clampQty(v) {
    const n = Number(String(v ?? "").trim());
    if (!Number.isFinite(n) || n < 1) return 1;
    return Math.floor(n);
  }

  function flash(
    text,
    variant = "danger",
    { persist = false, timeout = 3000 } = {},
  ) {
    if (!cartMsg) return;
    cartMsg.innerHTML = `<div class="alert alert-${variant} py-2 mb-0" role="alert">${text}</div>`;
    if (!persist) {
      window.setTimeout(() => {
        if (cartMsg) cartMsg.innerHTML = "";
      }, timeout);
    }
  }

  function setEmpty(isEmpty) {
    if (cartEmptyEl) cartEmptyEl.classList.toggle("d-none", !isEmpty);
    if (cartItemsEl) cartItemsEl.classList.toggle("d-none", isEmpty);
    if (checkoutBtn) checkoutBtn.disabled = isEmpty;
  }

  function resolveProductImage(imageValue) {
    if (!imageValue) return "";
    return String(imageValue);
  }

  async function fetchCart() {
    if (!window.CartAPI?.getCart) {
      throw new Error(
        "CartAPI not found. Ensure carts/cart.js is loaded in base.html",
      );
    }
    return window.CartAPI.getCart();
  }

  // ---- REQUIRED: each row has name, producer, qty input, unit label, unit_price, line_total, remove btn
  function buildItemRow(item) {
    const product = item.product || {};
    const itemId = item.id;
    const productId = product.id;

    const name = product.name ?? "Product";
    const producer = product.producer_name ?? "";
    const unitLabelText = product.unit ?? "";

    const qty = toNum(item.quantity ?? 1, 1);
    const unitPrice = toNum(item.unit_price ?? 0, 0);
    const lineTotal = toNum(item.line_total ?? qty * unitPrice, qty * unitPrice);

    // New fields (from backend)
    const baseUnitPrice = toNum(product.base_unit_price ?? 0, 0);
    const isWholesale = baseUnitPrice > 0 && unitPrice > 0 && unitPrice < baseUnitPrice;
    const savingsTotal = isWholesale ? (baseUnitPrice - unitPrice) * qty : 0;

    const stockQty = toNum(product.stock_quantity ?? 0, 0);
    const isOutOfStock = stockQty <= 0;

    const row = document.createElement("div");
    row.className =
      "cart-row border rounded p-3 mb-3 d-flex gap-3 align-items-start";
    row.dataset.itemId = String(itemId ?? "");
    row.dataset.productId = String(productId ?? "");

    // image (optional)
    const imgUrl = resolveProductImage(product.image);
    const imgWrap = document.createElement("div");
    imgWrap.className = "bg-light rounded flex-shrink-0 overflow-hidden";
    imgWrap.style.width = "64px";
    imgWrap.style.height = "64px";
    if (imgUrl) {
      imgWrap.innerHTML = `<img src="${imgUrl}" alt="${name}" style="width:100%;height:100%;object-fit:cover;" loading="lazy">`;
    }

    // meta (name + producer + badges)
    const meta = document.createElement("div");
    meta.innerHTML = `
      <div class="fw-semibold d-flex flex-wrap align-items-center gap-2">
        <span>${name}</span>
        ${isOutOfStock ? `<span class="badge text-bg-danger">Out of stock</span>` : ""}
        ${isWholesale ? `<span class="badge text-bg-success">Wholesale</span>` : ""}
      </div>
      ${producer ? `<div class="text-muted small">${producer}</div>` : ""}
      ${
        isWholesale
          ? `<div class="small text-success mt-1">You save ${money(savingsTotal)} on this item</div>`
          : ``
      }
    `;

    // qty editor + unit label
    const qtyWrap = document.createElement("div");
    qtyWrap.className = "d-flex align-items-center gap-2";

    const minus = document.createElement("button");
    minus.type = "button";
    minus.className = "btn btn-outline-secondary btn-sm";
    minus.textContent = "−";

    const qtyInput = document.createElement("input");
    qtyInput.type = "text";
    qtyInput.className = "form-control form-control-sm text-center";
    qtyInput.style.width = "72px";
    qtyInput.value = String(qty);
    qtyInput.inputMode = "numeric";
    qtyInput.autocomplete = "off";

    const plus = document.createElement("button");
    plus.type = "button";
    plus.className = "btn btn-outline-secondary btn-sm";
    plus.textContent = "+";

    const unitLabel = document.createElement("span");
    unitLabel.className = "text-muted small";
    unitLabel.textContent = unitLabelText;

    qtyWrap.append(minus, qtyInput, plus, unitLabel);

    // prices (professional: show was->now when wholesale)
    const prices = document.createElement("div");
    prices.className = "text-end";
    prices.innerHTML = isWholesale
      ? `
        <div class="small text-muted">
          Unit:
          <span class="text-decoration-line-through">${money(baseUnitPrice)}</span>
          <span class="ms-1 fw-semibold text-success">${money(unitPrice)}</span>
        </div>
        <div class="fw-semibold">Line: ${money(lineTotal)}</div>
      `
      : `
        <div class="small text-muted">Unit: ${money(unitPrice)}</div>
        <div class="fw-semibold">Line: ${money(lineTotal)}</div>
      `;

    // remove
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn btn-outline-danger btn-sm";
    removeBtn.textContent = "Remove";

    function setDisabled(disabled) {
      minus.disabled = disabled;
      plus.disabled = disabled;
      qtyInput.disabled = disabled;
      removeBtn.disabled = disabled;
    }

    if (isOutOfStock) {
      row.classList.add("is-oos");
      minus.disabled = true;
      plus.disabled = true;
      qtyInput.disabled = true;
      removeBtn.disabled = false;
    }

    async function commitQty(newQty) {
      const q = clampQty(newQty);
      setDisabled(true);
      try {
        await window.CartAPI.setItemQuantity({ productId, quantity: q });
        window.CartAPI.showToast?.(`Updated quantity to ${q}`, {
          title: "Cart",
          variant: "success",
          delay: 1800,
        });
        await refresh();
      } catch (e) {
        const m = e?.message ? e.message : String(e);
        flash(`Update failed: ${m}`, "danger", { persist: true });
      } finally {
        setDisabled(false);
      }
    }

    minus.addEventListener("click", () =>
      commitQty(clampQty(qtyInput.value) - 1),
    );
    plus.addEventListener("click", () =>
      commitQty(clampQty(qtyInput.value) + 1),
    );
    qtyInput.addEventListener("change", () =>
      commitQty(clampQty(qtyInput.value)),
    );

    removeBtn.addEventListener("click", async () => {
      const ok = window.confirm(`Remove “${name}” from your cart?`);
      if (!ok) return;

      setDisabled(true);
      try {
        await window.CartAPI.removeItem({ productId });
        window.CartAPI.showToast?.(`Removed “${name}”`, {
          title: "Cart",
          variant: "success",
          delay: 1800,
        });
        await refresh();
      } catch (e) {
        const m = e?.message ? e.message : String(e);
        flash(`Remove failed: ${m}`, "danger", { persist: true });
      } finally {
        setDisabled(false);
      }
    });

    row.append(imgWrap, meta, qtyWrap, prices, removeBtn);
    return row;
  }

  function render(cart) {
    const items = cart?.items ?? [];
    const hasOutOfStock = items.some(
      (it) => toNum(it?.product?.stock_quantity ?? 0) <= 0,
    );

    cartItemsEl?.replaceChildren();

    if (!items.length) {
      setEmpty(true);
    } else {
      setEmpty(false);
      for (const it of items) {
        cartItemsEl.appendChild(buildItemRow(it));
      }
    }

    if (checkoutBtn) {
      checkoutBtn.disabled = !items.length || hasOutOfStock;
    }

    if (hasOutOfStock) {
      flash(
        "Some items are out of stock. Remove them to proceed to checkout.",
        "warning",
        { persist: true },
      );
    }

    // Professional summary: show wholesale savings if any
    const distinct = items.length;
    const totalQty = toNum(cart?.total_quantity ?? 0, 0);

    let actualSubtotal = 0;
    let baseSubtotal = 0;

    for (const it of items) {
      const qty = toNum(it.quantity ?? 0, 0);
      const unitPrice = toNum(it.unit_price ?? 0, 0);
      const baseUnit = toNum(it?.product?.base_unit_price ?? 0, 0);

      actualSubtotal += unitPrice * qty;
      baseSubtotal += baseUnit * qty;
    }

    const wholesaleSavings = Math.max(0, baseSubtotal - actualSubtotal);
    const showSavings = wholesaleSavings > 0.009;

    distinctItemsEl && (distinctItemsEl.textContent = String(distinct));
    totalQtyEl && (totalQtyEl.textContent = String(totalQty));

    // Keep existing IDs, but upgrade meaning:
    // - subtotal: actual payable subtotal
    // - total: same as subtotal for now (no shipping/tax in your UI)
    subtotalEl && (subtotalEl.textContent = money(actualSubtotal));
    totalEl && (totalEl.textContent = money(actualSubtotal));

    // Inject “before wholesale” + “savings” rows into summary (professional look)
    const summaryCard = subtotalEl?.closest(".cart-card");
    if (summaryCard) {
      // Remove old injected block if exists
      const old = document.getElementById("wholesaleSummaryExtra");
      if (old) old.remove();

      if (showSavings) {
        const hr = summaryCard.querySelector("hr");
        if (hr) {
          const extra = document.createElement("div");
          extra.id = "wholesaleSummaryExtra";
          extra.className = "mb-2";
          extra.innerHTML = `
            <div class="d-flex justify-content-between mb-2">
              <span class="text-muted">Subtotal (before wholesale)</span>
              <span class="text-muted">${money(baseSubtotal)}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
              <span class="text-success fw-semibold">Wholesale savings</span>
              <span class="text-success fw-semibold">- ${money(wholesaleSavings)}</span>
            </div>
            <div class="alert alert-success py-2 mb-0">
              <strong>Nice!</strong> You saved <strong>${money(wholesaleSavings)}</strong> with wholesale pricing.
            </div>
          `;
          hr.parentNode.insertBefore(extra, hr); // insert above Total block
        }
      }
    }
  }

  async function refresh() {
    const cart = await fetchCart();
    render(cart);
  }

  checkoutBtn?.addEventListener("click", () => {
    window.location.href = "/orders/checkout";
  });

  refresh().catch((e) => {
    const m = e?.message ? e.message : String(e);
    flash(`Failed to load cart: ${m}`, "danger", { persist: true });
    setEmpty(true);
  });

  document.addEventListener("cart:updated", () => {
    refresh().catch(() => {});
  });
});