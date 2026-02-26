(() => {
  const API_BASE = "/api/cart/";
  const GUEST_TOKEN_KEY = "guest_token";

  const $ = (sel) => document.querySelector(sel);

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function money(value) {
    const n = Number(value ?? 0);
    if (Number.isNaN(n)) return "£0.00";
    return `£${n.toFixed(2)}`;
  }

  function resolveImageUrl(img) {
    if (!img) return "";
    // If API starts returning full URLs later, this still works.
    if (img.startsWith("http://") || img.startsWith("https://")) return img;
    if (img.startsWith("/")) return img;

    // Most common setups: MEDIA_URL is /media/
    return `/media/${img}`;
  }

  // ---------- CSRF (needed for session-auth unsafe methods) ----------
  // Django recommends sending X-CSRFToken header for AJAX requests. :contentReference[oaicite:4]{index=4}
  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const c of cookies) {
      const cookie = c.trim();
      if (cookie.startsWith(name + "=")) {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return null;
  }

  function getGuestToken() {
    try {
      return localStorage.getItem(GUEST_TOKEN_KEY);
    } catch {
      return null;
    }
  }

  function setGuestToken(token) {
    try {
      localStorage.setItem(GUEST_TOKEN_KEY, token);
    } catch {
      // ignore
    }
  }

  function setNavbarCount(count) {
    const badge = $("#cartCount");
    if (!badge) return;
    badge.textContent = String(count ?? 0);
  }

  async function fetchJson(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");

    const csrftoken = getCookie("csrftoken");
    const isUnsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);
    if (isUnsafe && csrftoken) headers.set("X-CSRFToken", csrftoken);

    const guestToken = getGuestToken();
    if (guestToken) headers.set("X-Guest-Token", guestToken);

    const res = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers,
    });

    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await res.json();
    }

    if (res.status === 400 && data && data.guest_token && !getGuestToken()) {
      const token = await createGuestCartToken();
      if (token) {
        return fetchJson(url, options); // retry once
      }
    }

    if (!res.ok) {
      const msg =
        (data && (data.detail || data.cart || JSON.stringify(data))) ||
        `Request failed (${res.status})`;
      const err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }

    return data;
  }

  async function createGuestCartToken() {
    const payload = await fetchJson(`${API_BASE}guest-token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (payload && payload.guest_token) {
      setGuestToken(payload.guest_token);
      return payload.guest_token;
    }
    return null;
  }

  async function getCart() {
    return fetchJson(API_BASE, { method: "GET" });
  }

  async function setItemQuantity(productId, quantity) {
    return fetchJson(`${API_BASE}items/${productId}/quantity/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity }),
    });
  }

  async function removeItem(productId) {
    return fetchJson(`${API_BASE}items/${productId}/`, { method: "DELETE" });
  }

  async function checkoutCart() {
    return fetchJson(`${API_BASE}checkout/`, { method: "POST" });
  }

  // ---------- Cart Page Rendering ----------
  function showMsg(kind, text) {
    const box = $("#cartMsg");
    if (!box) return;
    const cls =
      kind === "success"
        ? "alert alert-success"
        : kind === "warning"
          ? "alert alert-warning"
          : "alert alert-danger";
    box.innerHTML = `<div class="${cls}" role="alert">${escapeHtml(text)}</div>`;
  }

  function clearMsg() {
    const box = $("#cartMsg");
    if (!box) return;
    box.innerHTML = "";
  }

  function renderCart(cart) {
    // navbar badge always updates (all pages)
    setNavbarCount(cart?.total_quantity ?? 0);

    // if not on /cart/ page, stop here
    const itemsHost = $("#cartItems");
    if (!itemsHost) return;

    const emptyBox = $("#cartEmpty");
    const distinct = $("#sumDistinct");
    const qty = $("#sumQty");
    const subtotal = $("#sumSubtotal");
    const total = $("#sumTotal");

    if (distinct) distinct.textContent = String(cart?.distinct_items ?? 0);
    if (qty) qty.textContent = String(cart?.total_quantity ?? 0);
    if (subtotal) subtotal.textContent = money(cart?.subtotal ?? 0);
    if (total) total.textContent = money(cart?.total ?? 0);

    const items = Array.isArray(cart?.items) ? cart.items : [];
    if (!items.length) {
      itemsHost.innerHTML = "";
      if (emptyBox) emptyBox.classList.remove("d-none");
      return;
    }
    if (emptyBox) emptyBox.classList.add("d-none");

    itemsHost.innerHTML = items
      .map((it) => {
        const p = it.product || {};
        const img = resolveImageUrl(p.image);
        return `
          <div class="border rounded p-3 mb-3" data-product-id="${p.id}">
            <div class="d-flex gap-3">
              <div style="width:84px;flex:0 0 84px">
                ${
                  img
                    ? `<img src="${escapeHtml(img)}" alt="${escapeHtml(p.name)}" class="img-fluid rounded">`
                    : `<div class="bg-light rounded" style="width:84px;height:84px"></div>`
                }
              </div>

              <div class="flex-grow-1">
                <div class="d-flex justify-content-between align-items-start gap-3">
                  <div>
                    <div class="fw-semibold">${escapeHtml(p.name)}</div>
                    <div class="text-muted small">
                      ${escapeHtml(p.unit || "")}
                      ${
                        p.producer?.farm_name
                          ? ` • ${escapeHtml(p.producer.farm_name)}`
                          : ""
                      }
                    </div>
                  </div>

                  <div class="text-end">
                    <div class="small text-muted">Unit</div>
                    <div class="fw-semibold">${escapeHtml(it.unit_price)}</div>
                  </div>
                </div>

                <div class="d-flex align-items-center justify-content-between mt-3">
                  <div class="btn-group" role="group" aria-label="Quantity controls">
                    <button class="btn btn-outline-secondary btn-sm" data-action="dec" type="button">-</button>
                    <span class="btn btn-outline-secondary btn-sm disabled" aria-label="Quantity">
                      ${escapeHtml(it.quantity)}
                    </span>
                    <button class="btn btn-outline-secondary btn-sm" data-action="inc" type="button">+</button>
                  </div>

                  <div class="d-flex align-items-center gap-3">
                    <div class="text-end">
                      <div class="small text-muted">Line total</div>
                      <div class="fw-semibold">${money(it.line_total)}</div>
                    </div>

                    <button class="btn btn-outline-danger btn-sm" data-action="del" type="button">
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function refreshCart() {
    try {
      const cart = await getCart();
      renderCart(cart);
    } catch (e) {
      // if on cart page, show error; otherwise fail silently
      if ($("#cartItems")) showMsg("error", e.message || "Failed to load cart.");
      setNavbarCount(0);
    }
  }

  function bindCartPageEvents() {
    const host = $("#cartItems");
    if (!host) return;

    host.addEventListener("click", async (ev) => {
      const btn = ev.target.closest("[data-action]");
      if (!btn) return;

      clearMsg();

      const card = btn.closest("[data-product-id]");
      const productId = Number(card?.getAttribute("data-product-id"));
      if (!productId) return;

      try {
        // read current qty from the disabled middle button
        const qtyEl = card.querySelector('[aria-label="Quantity"]');
        const currentQty = Number(qtyEl?.textContent ?? 0);

        const action = btn.getAttribute("data-action");
        let cart;

        if (action === "inc") {
          cart = await setItemQuantity(productId, currentQty + 1);
          showMsg("success", "Quantity increased.");
        } else if (action === "dec") {
          if (currentQty <= 1) {
            cart = await removeItem(productId);
            showMsg("success", "Item removed.");
          } else {
            cart = await setItemQuantity(productId, currentQty - 1);
            showMsg("success", "Quantity decreased.");
          }
        } else if (action === "del") {
          cart = await removeItem(productId); // completely deletes item
          showMsg("success", "Item deleted.");
        }

        if (cart) {
          renderCart(cart);
          window.dispatchEvent(new CustomEvent("brfn:cart-updated", { detail: { cart } }));
        }
      } catch (e) {
        showMsg("error", e.message || "Cart update failed.");
      }
    });

    const checkoutBtn = $("#checkoutBtn");
    if (checkoutBtn) {
      checkoutBtn.addEventListener("click", async () => {
        clearMsg();
        checkoutBtn.disabled = true;

        try {
          const cart = await checkoutCart();
          renderCart(cart);
          window.dispatchEvent(new CustomEvent("brfn:cart-updated", { detail: { cart } }));

          // requirement: go to /orders/checkout
          window.location.href = "/orders/checkout";
        } catch (e) {
          showMsg("error", e.message || "Checkout failed.");
        } finally {
          checkoutBtn.disabled = false;
        }
      });
    }
  }


  window.BRFNCart = {
    refresh: refreshCart,
    setFromCart(cart) {
      if (!cart) return;
      renderCart(cart);
      window.dispatchEvent(new CustomEvent("brfn:cart-updated", { detail: { cart } }));
    },
  };

  // Any page can emit this event to update navbar badge:
  window.addEventListener("brfn:cart-updated", (e) => {
    const cart = e.detail?.cart;
    if (cart) setNavbarCount(cart.total_quantity ?? 0);
  });

  // Init
  document.addEventListener("DOMContentLoaded", () => {
    refreshCart();      // updates navbar count everywhere
    bindCartPageEvents(); // only does something on /cart/ page
  });
})();