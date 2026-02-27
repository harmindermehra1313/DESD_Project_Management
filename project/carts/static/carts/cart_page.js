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
    const s = String(imageValue);
    return s;
  }

  async function fetchCart() {
    if (!window.CartAPI?.getCart) {
      throw new Error(
        "CartAPI not found. Ensure carts/cart.js is loaded in base.html",
      );
    }
    return window.CartAPI.getCart();
  }

  // ---- REQUIRED: each row has name, producer, qty input, unit label, unit_price, line_total, remove btn, data-item-id
  function buildItemRow(item) {
    const product = item.product || {};
    const itemId = item.id; // cart line id from API
    const productId = product.id; // product id (used for PATCH/DELETE)

    const name = product.name ?? "Product";
    const producer = product.producer_name ?? "";
    const unit = product.unit ?? "";

    const qty = Number(item.quantity ?? 1);
    const unitPrice = Number(item.unit_price ?? 0);
    const lineTotal = Number(item.line_total ?? qty * unitPrice);

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

    // meta (name + producer)
    const meta = document.createElement("div");
    meta.className = "flex-grow-1";
    meta.innerHTML = `
      <div class="fw-semibold">${name}</div>
      ${producer ? `<div class="text-muted small">${producer}</div>` : ""}
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
    unitLabel.textContent = unit;

    qtyWrap.append(minus, qtyInput, plus, unitLabel);

    // prices
    const prices = document.createElement("div");
    prices.className = "text-end";
    prices.innerHTML = `
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
        const msg = e?.message ? e.message : String(e);
        flash(`Update failed: ${msg}`, "danger", { persist: true });
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
      // Confirmation prompt
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
        const msg = e?.message ? e.message : String(e);
        flash(`Remove failed: ${msg}`, "danger", { persist: true });
      } finally {
        setDisabled(false);
      }
    });

    row.append(imgWrap, meta, qtyWrap, prices, removeBtn);
    return row;
  }

  function render(cart) {
    const items = cart?.items ?? [];

    cartItemsEl?.replaceChildren();

    if (!items.length) {
      setEmpty(true);
    } else {
      setEmpty(false);
      for (const it of items) {
        cartItemsEl.appendChild(buildItemRow(it));
      }
    }
    const distinct = items.length;
    const totalQty = Number(cart?.total_quantity ?? 0);
    const subtotal = items.reduce(
      (acc, it) => acc + Number(it.line_total ?? 0),
      0,
    );

    distinctItemsEl && (distinctItemsEl.textContent = String(distinct));
    totalQtyEl && (totalQtyEl.textContent = String(totalQty));
    subtotalEl && (subtotalEl.textContent = money(subtotal));
    totalEl && (totalEl.textContent = money(subtotal));
  }

  async function refresh() {
    const cart = await fetchCart();
    render(cart);
  }

  checkoutBtn?.addEventListener("click", () => {
    window.location.href = "/orders/checkout";
  });

  refresh().catch((e) => {
    const msg = e?.message ? e.message : String(e);
    flash(`Failed to load cart: ${msg}`, "danger", { persist: true });
    setEmpty(true);
  });

  // Optional: refresh cart page if other pages add items
  document.addEventListener("cart:updated", () => {
    refresh().catch(() => {});
  });
});
