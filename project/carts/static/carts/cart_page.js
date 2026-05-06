// added food miles - joe
const M = window.CartPageMessages;
// carts/static/carts/cart_page.js
document.addEventListener("DOMContentLoaded", () => {
  const cartMsg = document.getElementById("cartMsg");
  const cartItemsEl = document.getElementById("cartItems");
  const cartEmptyEl = document.getElementById("cartEmpty");

  const distinctItemsEl = document.getElementById("distinctItems");
  const totalQtyEl = document.getElementById("totalQty");
  const subtotalEl = document.getElementById("subtotal");
  const totalEl = document.getElementById("total");
  const totalFoodMilesEl = document.getElementById("totalFoodMiles");

  const checkoutBtn = document.getElementById("checkoutBtn");

  const GBP = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  });

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

  function getItemStatus(product) {
    const stockQty = toNum(product?.stock_quantity ?? 0, 0);
    const isExpired = Boolean(product?.is_expired);
    const isOutOfStock = stockQty <= 0;
    const isPurchasable =
      typeof product?.is_purchasable === "boolean"
        ? product.is_purchasable
        : !isExpired && !isOutOfStock;

    return {
      stockQty,
      isExpired,
      isOutOfStock,
      isPurchasable,
      isBlocked: isExpired || isOutOfStock || !isPurchasable,
    };
  }

  function getBlockedMessage(product) {
    return M.getBlockedMessage(product);
  }

  function money(v) {
    const n = Number(v);
    return GBP.format(Number.isFinite(n) ? n : 0);
  }
  function round2(n) {
    return Math.round((Number(n) || 0) * 100) / 100;
  }

  function approxEqual(a, b, eps = 0.01) {
    return Math.abs((Number(a) || 0) - (Number(b) || 0)) <= eps;
  }

  function computeSurplusUnitPrice(baseUnitPrice, surplusPercent) {
    const base = toNum(baseUnitPrice, 0);
    const pct = toNum(surplusPercent, 0);
    if (!(base > 0) || !(pct > 0)) return null;
    const discounted = base * (1 - pct / 100);
    return round2(discounted);
  }

  function hasMeaningfulNote(note) {
    const s = String(note ?? "").trim();
    if (!s) return false;
    return s.toLowerCase() !== "none";
  }
  function toNum(v, fallback = 0) {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  function parseMiles(v) {
    if (v === null || v === undefined || v === "") return NaN;
    const n = Number(v);
    return Number.isFinite(n) ? n : NaN;
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

  async function fetchCart() {
    if (!window.CartAPI?.getCart) {
      throw new Error(M.cartApiMissing);
    }
    return window.CartAPI.getCart();
  }

  function buildItemRow(item, foodMilesLoginRequired = false) {
    const product = item.product || {};
    const itemId = item.id;
    const inventoryId = Number(item.inventory_id ?? 0);
    const productId = Number(product.id ?? item.product_id ?? 0);
    const productUrl = productId ? `/products/${productId}/` : "#";

    const name = product.name ?? M.productFallback;
    const producer = product.producer_name ?? "";
    const unitLabelText = product.unit ?? "";

    const qty = toNum(item.quantity ?? 1, 1);
    const unitPrice = toNum(item.unit_price ?? 0, 0);
    const lineTotal = toNum(
      item.line_total ?? qty * unitPrice,
      qty * unitPrice,
    );
    const foodMiles = parseMiles(item.food_miles);
    const lineFoodMiles = parseMiles(item.line_food_miles);
    const producerId = Number(product.producer_id ?? NaN);

    const baseUnitPrice = toNum(product.base_unit_price ?? 0, 0);

    const surplusStatus = String(product.surplus_status ?? "");
    const surplusPercent = toNum(product.surplus_discount_percentage ?? 0, 0);
    const surplusNote = String(product.surplus_note ?? "");

    const expectedSurplusUnit = computeSurplusUnitPrice(
      baseUnitPrice,
      surplusPercent,
    );

    const unitIsDiscounted =
      baseUnitPrice > 0 && unitPrice > 0 && unitPrice < baseUnitPrice;

    const isSurplus =
      surplusStatus === "SA" &&
      expectedSurplusUnit !== null &&
      approxEqual(unitPrice, expectedSurplusUnit);

    const isWholesale = unitIsDiscounted && !isSurplus;

    const wholesaleSavingsTotal = isWholesale
      ? (baseUnitPrice - unitPrice) * qty
      : 0;
    const surplusSavingsTotal = isSurplus
      ? (baseUnitPrice - unitPrice) * qty
      : 0;

    const { isExpired, isOutOfStock, isPurchasable, isBlocked, stockQty } =
      getItemStatus(product);
    const rowFoodMilesLoginRequired = Boolean(foodMilesLoginRequired);

    const row = document.createElement("div");
    row.className = "cart-row mb-3";
    row.dataset.itemId = String(itemId ?? "");
    row.dataset.inventoryId = String(item.inventory_id ?? "");

    const placeholder =
      cartItemsEl?.dataset?.placeholderImg || "/static/img/default-product.png";

    let imgSrc = String(product.image ?? "").trim();
    if (!imgSrc) imgSrc = placeholder;
    else if (!imgSrc.startsWith("/") && !/^https?:\/\//i.test(imgSrc)) {
      imgSrc = `/media/${imgSrc}`;
    }

    const imgWrap = document.createElement("div");
    imgWrap.className = "cart-thumb-wrap";
    imgWrap.innerHTML = `
    <img
      class="cart-thumb"
      src="${imgSrc}"
      alt="${name}"
      loading="lazy"
      onerror="this.onerror=null;this.src='${placeholder}';"
    >
  `;

    const meta = document.createElement("div");
    meta.className = "cart-meta";
    meta.innerHTML = `
    <div class="cart-name-row fw-semibold d-flex flex-wrap align-items-center gap-2">
      <a href="${productUrl}" class="cart-product-link text-decoration-none">
        ${name}
      </a>
      ${isExpired ? `<span class="badge text-bg-danger">${M.expiredBadge}</span>` : ""}
      ${isOutOfStock ? `<span class="badge text-bg-danger">${M.outOfStockBadge}</span>` : ""}
      ${isWholesale ? `<span class="badge text-bg-warning">${M.wholesaleBadge}</span>` : ""}
      ${isSurplus ? `<span class="badge text-bg-danger">${M.surplusBadge}</span>` : ""}
    </div>
    ${producer ? `<div class="text-muted small">${producer}</div>` : ""}
    ${Number.isFinite(foodMiles) ? `<div class="small text-muted mt-1" style="background-color: #d4edda; padding: 0.5rem; border-radius: 0.25rem; border-left: 3px solid #28a745; color: #155724;">Food miles: ${foodMiles.toFixed(2)} miles from this producer</div>` : `<div class="small text-muted mt-1">${rowFoodMilesLoginRequired ? "Log in to see your food miles" : "Food miles unavailable for this route"}</div>`}
    ${
      product.expiry_date
        ? `<div class="small mt-1 ${isExpired ? "text-danger fw-semibold" : "text-muted"}">
             ${M.getExpiryLabel(product)}: ${formatDate(product.expiry_date)}
           </div>`
        : ``
    }
    ${
      isBlocked
        ? `<div class="small text-danger mt-1">${getBlockedMessage(product)}</div>`
        : ``
    }
    ${
      isWholesale
        ? `<div class="small text-success mt-1">${M.saveWithWholesale(money(wholesaleSavingsTotal))}</div>`
        : ``
    }
    ${
      isSurplus
        ? `<div class="small text-danger mt-1">
         <div>${M.saveWithSurplus(money(surplusSavingsTotal))}</div>
         <div>
           <span class="fw-semibold">${M.surplusReasonLabel}:</span>
           ${M.getSurplusReason(surplusNote)}
         </div>
       </div>`
        : ``
    }
  `;

    const rowMsg = document.createElement("div");
    rowMsg.className = "cart-row-msg mt-2";
    rowMsg.setAttribute("aria-live", "polite");
    meta.appendChild(rowMsg);

    function flashRow(text, variant = "warning") {
      rowMsg.innerHTML = `
      <div class="alert alert-${variant} py-2 px-3 mb-0" role="alert">
        ${text}
      </div>
    `;
    }

    function clearRowFlash() {
      rowMsg.innerHTML = "";
    }
    function showCartToast(message, variant = "warning", delay = 3000) {
      try {
        if (window.CartAPI?.showToast) {
          window.CartAPI.showToast(message, {
            title: M.minimumQuantityTitle,
            variant,
            delay,
          });
          return;
        }
      } catch {
        // Fall back to the row-level message if the toast container is unavailable.
      }

      flashRow(message, variant);
    }

    const qtyWrap = document.createElement("div");
    qtyWrap.className = "cart-qty";

    const minus = document.createElement("button");
    minus.type = "button";
    minus.className = "qty-btn";
    minus.textContent = "−";

    const qtyInput = document.createElement("input");
    qtyInput.type = "text";
    qtyInput.className = "qty-input";
    qtyInput.value = String(qty);
    qtyInput.inputMode = "numeric";
    qtyInput.autocomplete = "off";

    const plus = document.createElement("button");
    plus.type = "button";
    plus.className = "qty-btn";
    plus.textContent = "+";

    const unitLabel = document.createElement("span");
    unitLabel.className = "cart-unit";
    unitLabel.textContent = unitLabelText;

    qtyWrap.append(minus, qtyInput, plus, unitLabel);

    const prices = document.createElement("div");
    prices.className = "cart-prices";
    const showWasNow =
      (isWholesale || isSurplus) &&
      baseUnitPrice > 0 &&
      unitPrice > 0 &&
      unitPrice < baseUnitPrice;

    prices.innerHTML = showWasNow
      ? `
      <div class="small text-muted">
        ${M.unitLabelPrefix}:
        <span class="text-decoration-line-through">${money(baseUnitPrice)}</span>
        <span class="ms-1 fw-semibold ${isWholesale ? "text-success" : "text-danger"}">${money(unitPrice)}</span>
      </div>
      <div class="fw-semibold">${M.lineLabel(money(lineTotal))}</div>
    `
      : `
      <div class="small text-muted">${M.unitLabel(money(unitPrice))}</div>
      <div class="fw-semibold">${M.lineLabel(money(lineTotal))}</div>
    `;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn btn-danger btn-sm cart-remove-btn";
    removeBtn.textContent = M.removeButton;

    function setDisabled(disabled) {
      minus.disabled = disabled;
      plus.disabled = disabled;
      qtyInput.disabled = disabled;
      removeBtn.disabled = disabled;
    }

    if (isBlocked) {
      row.classList.add("is-oos");
      minus.disabled = true;
      plus.disabled = true;
      qtyInput.disabled = true;
      removeBtn.disabled = false;
    }

    async function commitQty(newQty) {
      clearRowFlash();

      if (isBlocked) {
        flashRow(getBlockedMessage(product), "danger");
        return;
      }

      const rawQty = Number(String(newQty ?? "").trim());

      if (!Number.isFinite(rawQty) || rawQty < 1) {
        qtyInput.value = "1";
        showCartToast(M.minimumQuantityMessage(name), "danger", 3200);
        return;
      }

      const q = Math.floor(rawQty);

      setDisabled(true);
      try {
        await window.CartAPI.setItemQuantity({ inventoryId, quantity: q });

        window.CartAPI.showToast?.(M.updatedQuantity(q), {
          title: M.cartTitle,
          variant: "success",
          delay: 1800,
        });

        await refresh();
      } catch (e) {
        const message = M.getRowUpdateError(e, product, q);
        const variant =
          M.isInventoryLimitError(e) || /expired|unavailable/i.test(message)
            ? "warning"
            : "danger";

        flashRow(message, variant);
      } finally {
        setDisabled(false);
      }
    }

    minus.addEventListener("click", () => {
      const currentQty = clampQty(qtyInput.value);

      if (currentQty <= 1) {
        qtyInput.value = "1";
        clearRowFlash();

        showCartToast(M.minimumQuantityMessage(name), "danger", 3200);
        return;
      }

      commitQty(currentQty - 1);
    });

    plus.addEventListener("click", () =>
      commitQty(clampQty(qtyInput.value) + 1),
    );

    qtyInput.addEventListener("input", clearRowFlash);

    qtyInput.addEventListener("change", () =>
      commitQty(clampQty(qtyInput.value)),
    );

    removeBtn.addEventListener("click", async () => {
      const ok = window.confirm(M.removeConfirm(name));
      if (!ok) return;

      setDisabled(true);
      try {
        await window.CartAPI.removeItem({ inventoryId });
        window.CartAPI.showToast?.(M.removedItem(name), {
          title: M.cartTitle,
          variant: "success",
          delay: 1800,
        });
        await refresh();
      } catch (e) {
        flash(M.getRemoveError(e), "danger", { persist: true });
      } finally {
        setDisabled(false);
      }
    });

    row.append(imgWrap, meta, qtyWrap, prices, removeBtn);
    return row;
  }

  function render(cart) {
    const items = cart?.items ?? [];
    const foodMilesLoginRequired = Boolean(cart?.food_miles_login_required);
    const hasBlockedItems = items.some((it) => {
      const status = getItemStatus(it?.product || {});
      return status.isBlocked;
    });

    cartItemsEl?.replaceChildren();

    if (!items.length) {
      setEmpty(true);
    } else {
      setEmpty(false);
      for (const it of items) {
        cartItemsEl.appendChild(buildItemRow(it, foodMilesLoginRequired));
      }
    }

    if (checkoutBtn) {
      checkoutBtn.disabled = !items.length || hasBlockedItems;
    }

    if (hasBlockedItems) {
      flash(M.blockedCheckout, "warning", { persist: true });
    } else if (cartMsg) {
      cartMsg.innerHTML = "";
    }

    // Professional summary: show wholesale savings if any
    const distinct = items.length;
    const totalQty = toNum(cart?.total_quantity ?? 0, 0);

    let actualSubtotal = 0;
    let baseSubtotal = 0;
    let wholesaleSavings = 0;
    let surplusSavings = 0;
    let totalFoodMiles = 0;
    let hasFoodMiles = false;
    const countedProducerIds = new Set();

    for (const it of items) {
      const qty = toNum(it.quantity ?? 0, 0);
      const unitPrice = toNum(it.unit_price ?? 0, 0);
      const baseUnit = toNum(it?.product?.base_unit_price ?? 0, 0);

      const surplusStatus = String(it?.product?.surplus_status ?? "");
      const surplusPercent = toNum(
        it?.product?.surplus_discount_percentage ?? 0,
        0,
      );
      const expectedSurplusUnit = computeSurplusUnitPrice(
        baseUnit,
        surplusPercent,
      );

      const lineActual = unitPrice * qty;
      const lineBase = baseUnit * qty;
      const foodMiles = parseMiles(it.food_miles);
      const producerId = Number(it?.product?.producer_id ?? NaN);

      actualSubtotal += lineActual;
      baseSubtotal += lineBase;

      if (
        Number.isFinite(foodMiles) &&
        Number.isFinite(producerId) &&
        !countedProducerIds.has(producerId)
      ) {
        countedProducerIds.add(producerId);
        totalFoodMiles += foodMiles;
        hasFoodMiles = true;
      }

      const unitIsDiscounted =
        baseUnit > 0 && unitPrice > 0 && unitPrice < baseUnit;
      const lineIsSurplus =
        surplusStatus === "SA" &&
        expectedSurplusUnit !== null &&
        approxEqual(unitPrice, expectedSurplusUnit);

      const lineIsWholesale = unitIsDiscounted && !lineIsSurplus;

      if (lineIsWholesale) wholesaleSavings += (baseUnit - unitPrice) * qty;
      if (lineIsSurplus) surplusSavings += (baseUnit - unitPrice) * qty;
    }

    wholesaleSavings = Math.max(0, wholesaleSavings);
    surplusSavings = Math.max(0, surplusSavings);

    const anySavings = wholesaleSavings + surplusSavings > 0.009;

    distinctItemsEl && (distinctItemsEl.textContent = String(distinct));
    totalQtyEl && (totalQtyEl.textContent = String(totalQty));

    // Keep existing IDs, but upgrade meaning:
    // - subtotal: actual payable subtotal
    // - total: same as subtotal for now (no shipping/tax in your UI)
    subtotalEl && (subtotalEl.textContent = money(actualSubtotal));
    totalEl && (totalEl.textContent = money(actualSubtotal));
    if (totalFoodMilesEl) {
      totalFoodMilesEl.textContent = hasFoodMiles
        ? `${totalFoodMiles.toFixed(2)} miles`
        : foodMilesLoginRequired
          ? "Log in to see your food miles"
          : "Unavailable";
    }

    // Inject “before wholesale” + “savings” rows into summary (professional look)
    const summaryCard = subtotalEl?.closest(".cart-card");
    if (summaryCard) {
      // Remove old injected block if exists
      const old = document.getElementById("wholesaleSummaryExtra");
      if (old) old.remove();

      if (anySavings) {
        const hr = summaryCard.querySelector("hr");
        if (hr) {
          const extra = document.createElement("div");
          extra.id = "wholesaleSummaryExtra";
          extra.className = "mb-2";

          const totalSavings = wholesaleSavings + surplusSavings;

          extra.innerHTML = `
            <div class="d-flex justify-content-between mb-2">
              <span class="text-muted">${M.subtotalBeforeDiscounts}</span>
              <span class="text-muted">${money(baseSubtotal)}</span>
            </div>

            ${
              wholesaleSavings > 0.009
                ? `<div class="d-flex justify-content-between mb-2">
                     <span class="text-success fw-semibold">${M.wholesaleSavings}</span>
                     <span class="text-success fw-semibold">- ${money(wholesaleSavings)}</span>
                   </div>`
                : ``
            }

            ${
              surplusSavings > 0.009
                ? `<div class="d-flex justify-content-between mb-2">
                     <span class="text-danger fw-semibold">${M.surplusSavings}</span>
                     <span class="text-danger fw-semibold">- ${money(surplusSavings)}</span>
                   </div>`
                : ``
            }

            <div class="alert alert-success py-2 mb-0">
              <strong>${M.savingsIntro}</strong> <strong>${M.savingsMessage(money(totalSavings))}</strong>
            </div>
          `;

          hr.parentNode.insertBefore(extra, hr);
        }
      }
    }
  }

  async function refresh() {
    const cart = await fetchCart();
    render(cart);
  }

  checkoutBtn?.addEventListener("click", () => {
    window.location.href = M.checkoutPath;
  });

  refresh().catch((e) => {
    flash(M.getLoadError(e), "danger", { persist: true });
    setEmpty(true);
  });

  document.addEventListener("cart:updated", (event) => {
    const action = event?.detail?.action;

    if (action === "set_qty" || action === "remove") {
      return;
    }

    refresh().catch(() => {});
  });
});
