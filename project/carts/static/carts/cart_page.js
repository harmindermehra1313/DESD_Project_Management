document.addEventListener("DOMContentLoaded", () => {
  const cartMsg = document.getElementById("cartMsg");
  const cartItemsEl = document.getElementById("cartItems");
  const cartEmptyEl = document.getElementById("cartEmpty");

  const distinctItemsEl = document.getElementById("distinctItems");
  const totalQtyEl = document.getElementById("totalQty");
  const subtotalEl = document.getElementById("subtotal");
  const totalEl = document.getElementById("total");

  const discountEl = document.getElementById("discount");
  const taxEl = document.getElementById("tax");
  const shippingEl = document.getElementById("shipping");

  const checkoutBtn = document.getElementById("checkoutBtn");

  const GBP = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });

  function money(v) {
    const n = Number(v);
    return GBP.format(Number.isFinite(n) ? n : 0);
  }

  // Best-practice flash: safe textContent, aria-live, success auto-dismiss, errors persist
  function flash(text, variant = "success", { timeout = 2500, persist = false } = {}) {
    cartMsg.replaceChildren();

    const alert = document.createElement("div");
    alert.className = `alert alert-${variant} py-2 mb-0`;
    alert.setAttribute("role", variant === "danger" ? "alert" : "status");
    alert.textContent = text;

    cartMsg.appendChild(alert);

    if (!persist && timeout > 0) {
      window.setTimeout(() => {
        if (cartMsg.contains(alert)) alert.remove();
      }, timeout);
    }
  }

  function resolveProductImage(imageValue) {
    // API returns "eggs.jpg" => we serve from /static/cart/eggs.jpg
    if (!imageValue) return "";
    if (imageValue.startsWith("http")) return imageValue;
    if (imageValue.startsWith("/")) return imageValue;
    return `/static/cart/${imageValue}`;
  }

  function clampQty(v) {
    const n = Number(v);
    if (!Number.isFinite(n) || n < 1) return 1;
    return Math.floor(n);
  }

  function setCheckoutEnabled(enabled) {
    if (!enabled) {
      checkoutBtn.classList.add("disabled");
      checkoutBtn.setAttribute("aria-disabled", "true");
      checkoutBtn.tabIndex = -1;
    } else {
      checkoutBtn.classList.remove("disabled");
      checkoutBtn.removeAttribute("aria-disabled");
      checkoutBtn.tabIndex = 0;
    }
  }

  function iconTrash() {
    return `
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
        <path fill="currentColor" d="M9 3h6l1 2h5v2H3V5h5l1-2zm1 7h2v9h-2v-9zm4 0h2v9h-2v-9zM6 8h12l-1 13H7L6 8z"/>
      </svg>
    `;
  }

  // Your cart JSON is stable now, so normalize is simple
  function normalizeCart(cart) {
    return {
      items: Array.isArray(cart.items) ? cart.items : [],
      distinct_items: Number(cart.distinct_items ?? 0),
      total_quantity: Number(cart.total_quantity ?? 0),
      subtotal: Number(cart.subtotal ?? 0),
      total: Number(cart.total ?? 0),
    };
  }

  function buildItemRow(item) {
    const product = item.product || {};
    const productId = product.id; // IMPORTANT: your API has product.id
    const name = product.name ?? "Product";
    const unit = product.unit ?? "";
    const unitPrice = Number(item.unit_price ?? product.price ?? 0);
    const qty = Number(item.quantity ?? 1);
    const imgUrl = resolveProductImage(product.image);

    const row = document.createElement("div");
    row.className = "cart-item";

    // image
    const imgWrap = document.createElement("div");
    imgWrap.className = "cart-item__img";
    if (imgUrl) {
      const img = document.createElement("img");
      img.src = imgUrl;
      img.alt = name;
      img.loading = "lazy";
      imgWrap.appendChild(img);
    } else {
      imgWrap.innerHTML = `<div class="text-muted small">No image</div>`;
    }

    // details
    const details = document.createElement("div");

    const title = document.createElement("div");
    title.className = "cart-item__title";
    title.textContent = name;

    const meta = document.createElement("div");
    meta.className = "cart-item__meta";
    const metaUnit = document.createElement("span");
    metaUnit.textContent = `Unit: ${unit}`;
    meta.appendChild(metaUnit);

    const price = document.createElement("div");
    price.className = "cart-item__price";
    price.textContent = money(unitPrice);

    details.appendChild(title);
    details.appendChild(meta);
    details.appendChild(price);

    // actions
    const actions = document.createElement("div");
    actions.className = "cart-item__actions";

    // qty controls
    const qtyWrap = document.createElement("div");
    qtyWrap.className = "qty";

    const minus = document.createElement("button");
    minus.type = "button";
    minus.textContent = "–";

    const qtyInput = document.createElement("input");
    qtyInput.type = "text";
    qtyInput.value = String(qty);
    qtyInput.inputMode = "numeric";
    qtyInput.autocomplete = "off";

    const plus = document.createElement("button");
    plus.type = "button";
    plus.textContent = "+";

    qtyWrap.appendChild(minus);
    qtyWrap.appendChild(qtyInput);
    qtyWrap.appendChild(plus);

    // delete
    const iconRow = document.createElement("div");
    iconRow.className = "d-flex gap-2";

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "icon-btn";
    delBtn.title = "Remove";
    delBtn.innerHTML = iconTrash();

    iconRow.appendChild(delBtn);

    actions.appendChild(qtyWrap);
    actions.appendChild(iconRow);

    function disableRow(disabled) {
      minus.disabled = disabled;
      plus.disabled = disabled;
      qtyInput.disabled = disabled;
      delBtn.disabled = disabled;
    }

    async function setQty(newQty) {
      const q = clampQty(newQty);
      disableRow(true);
      try {
        await window.CartAPI.setItemQuantity({ product: { id: productId } }, q);
        flash(`Updated “${name}” quantity to ${q}.`, "success", { timeout: 1800 });
        await refresh();
      } catch (e) {
        flash(`Update quantity failed: ${e.message}`, "danger", { persist: true });
      } finally {
        disableRow(false);
      }
    }

    minus.addEventListener("click", () => setQty(clampQty(qtyInput.value) - 1));
    plus.addEventListener("click", () => setQty(clampQty(qtyInput.value) + 1));
    qtyInput.addEventListener("change", () => setQty(clampQty(qtyInput.value)));

    delBtn.addEventListener("click", async () => {
      disableRow(true);
      try {
        await window.CartAPI.removeItem({ product: { id: productId } });
        flash(`Removed “${name}” from your cart.`, "success", { timeout: 2200 });
        await refresh();
      } catch (e) {
        flash(`Remove failed: ${e.message}`, "danger", { persist: true });
      } finally {
        disableRow(false);
      }
    });

    row.appendChild(imgWrap);
    row.appendChild(details);
    row.appendChild(actions);

    return row;
  }

  function render(cart) {
    const c = normalizeCart(cart);

    // Summary
    distinctItemsEl.textContent = String(c.distinct_items);
    totalQtyEl.textContent = String(c.total_quantity);
    subtotalEl.textContent = money(c.subtotal);
    totalEl.textContent = money(c.total);

    // If you don't implement these yet, keep them explicit/consistent:
    discountEl.textContent = money(0);
    taxEl.textContent = money(0);
    shippingEl.textContent = "Free";

    const isEmpty = c.items.length === 0;

    cartItemsEl.innerHTML = "";
    cartEmptyEl.classList.toggle("d-none", !isEmpty);
    setCheckoutEnabled(!isEmpty);

    if (!isEmpty) {
      for (const it of c.items) {
        cartItemsEl.appendChild(buildItemRow(it));
      }
    }
  }

  async function refresh() {
    try {
      if (!window.CartAPI) {
        flash("CartAPI not found. Ensure static/carts/cart.js is loaded in base.html.", "danger", { persist: true });
        return;
      }
      const cart = await window.CartAPI.getCart();
      render(cart);
    } catch (e) {
      flash(`Failed to load cart: ${e.message}`, "danger", { persist: true });
    }
  }

  refresh();
});