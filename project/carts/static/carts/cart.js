// carts/static/carts/cart.js
// Clean module: API client + badge sync + CartAPI bridge.
// No cart-page rendering and no legacy add-to-cart handlers.

const API_ROOT = "/api";

function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_ROOT}${p}`;
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const c of cookies) {
    const v = c.trim();
    if (v.startsWith(name + "="))
      return decodeURIComponent(v.slice(name.length + 1));
  }
  return null;
}

function getCsrfToken() {
  return getCookie("csrftoken");
}

async function parseJsonSafe(res) {
  const ct = res.headers?.get?.("content-type") || "";
  if (!ct.includes("application/json")) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

async function request(method, path, { body } = {}) {
  const headers = { Accept: "application/json" };

  const isMutating = !["GET", "HEAD", "OPTIONS"].includes(method);
  if (isMutating) {
    const csrf = getCsrfToken();
    if (!csrf)
      throw new Error("CSRF token not found (csrftoken cookie missing)");
    headers["X-CSRFToken"] = csrf;
  }

  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(apiUrl(path), {
    method,
    credentials: "include",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const data = await parseJsonSafe(res);


  function extractErrorMessage(data, fallback) {
    if (!data) return fallback;

    // DRF detail/error
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.error === "string") return data.error;

    // DRF field errors: {field: ["msg1", "msg2"]} or {field: "msg"}
    if (typeof data === "object") {
      const parts = [];
      for (const [key, val] of Object.entries(data)) {
        if (Array.isArray(val)) {
          for (const msg of val) {
            parts.push(
              key === "non_field_errors" ? String(msg) : `${key}: ${msg}`,
            );
          }
        } else if (typeof val === "string") {
          parts.push(key === "non_field_errors" ? val : `${key}: ${val}`);
        }
      }
      if (parts.length) return parts.join(" | ");
    }

    return fallback;
  }

  if (!res.ok) {
    const fallback = `Request failed (HTTP ${res.status})`;
    const msg = extractErrorMessage(data, fallback);
    const err = new Error(msg);
    err.status = res.status;
    err.payload = data;
    throw err;
  }

  return { res, data };
}

/** GET /api/cart/ */
export async function getCart() {
  const { data } = await request("GET", "/cart/");
  return data;
}

/** POST /api/cart/items/ */
// export async function addToCart({ productId, quantity = 1 } = {}) {
//   if (!Number.isInteger(productId) || productId <= 0) {
//     throw new Error("addToCart: productId must be a positive integer");
//   }
//   const q = Number(quantity);
//   if (!Number.isFinite(q) || q < 1) {
//     throw new Error("addToCart: quantity must be >= 1");
//   }

//   const { data } = await request("POST", "/cart/items/", {
//     body: { product_id: productId, quantity: q },
//   });

//   document.dispatchEvent(
//     new CustomEvent("cart:updated", { detail: { action: "add" } }),
//   );
//   await getCartBadgeCount().catch(() => {});
//   return data;
// }
export async function addToCart({ inventoryId, quantity = 1 } = {}) {
  console.log("DEBUG addToCart called with:", { inventoryId, quantity });
  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error("addToCart: inventoryId must be a positive integer");
  }

  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 1) {
    throw new Error("addToCart: quantity must be >= 1");
  }
  const payload = { inventory_id: inventoryId, quantity: q };
  console.log("DEBUG addToCart payload:", payload);
  const { data } = await request("POST", "/cart/items/", {
    body: payload,
  });

  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "add" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return data;
}

/** PATCH /api/cart/items/<product_id>/ */
// export async function setItemQuantity({ productId, quantity } = {}) {
//   if (!Number.isInteger(productId) || productId <= 0) {
//     throw new Error("setItemQuantity: productId must be a positive integer");
//   }
//   const q = Number(quantity);
//   if (!Number.isFinite(q) || q < 0) {
//     throw new Error("setItemQuantity: quantity must be >= 0");
//   }

//   const { res, data } = await request("PATCH", `/cart/items/${productId}/`, {
//     body: { quantity: q },
//   });

//   document.dispatchEvent(
//     new CustomEvent("cart:updated", { detail: { action: "set_qty" } }),
//   );
//   await getCartBadgeCount().catch(() => {});
//   if (res.status === 204) return null;
//   return data;
// }
export async function setItemQuantity({ inventoryId, quantity } = {}) {
  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error("setItemQuantity: inventoryId must be a positive integer");
  }

  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 0) {
    throw new Error("setItemQuantity: quantity must be >= 0");
  }

  const { res, data } = await request("PATCH", `/cart/items/${inventoryId}/`, {
    body: { quantity: q },
  });

  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "set_qty" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return res.status === 204 ? null : data;
}

/** DELETE /api/cart/items/<product_id>/ */
// export async function removeItem({ productId } = {}) {
//   if (!Number.isInteger(productId) || productId <= 0) {
//     throw new Error("removeItem: productId must be a positive integer");
//   }

//   await request("DELETE", `/cart/items/${productId}/`);
//   document.dispatchEvent(
//     new CustomEvent("cart:updated", { detail: { action: "remove" } }),
//   );
//   await getCartBadgeCount().catch(() => {});
//   return { ok: true };
// }
export async function removeItem({ inventoryId } = {}) {
  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error("removeItem: inventoryId must be a positive integer");
  }

  await request("DELETE", `/cart/items/${inventoryId}/`);
  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "remove" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return { ok: true };
}

/** Badge sync against #cartCount */
export async function getCartBadgeCount() {
  const badge = document.getElementById("cartCount");
  if (!badge) return 0;

  badge.textContent = "0";
  badge.classList.remove("is-hidden"); // always visible

  const cart = await getCart();
  const count = Number(cart?.total_quantity ?? 0);

  badge.textContent = String(count);
  // Do NOT hide when 0
  badge.classList.remove("is-hidden");

  return count;
}

// Init badge on every page load + keep in sync
document.addEventListener("DOMContentLoaded", () => {
  getCartBadgeCount().catch(() => {});
});
document.addEventListener("cart:updated", () => {
  getCartBadgeCount().catch(() => {});
});
function ensureToastContainer() {
  const el = document.getElementById("toast-container");
  if (!el)
    throw new Error(
      "toast-container not found (components/toast.html missing)",
    );
  return el;
}

function showToast(
  message,
  { title = "", variant = "success", delay = 2000 } = {},
) {
  const container = ensureToastContainer();

  const toastEl = document.createElement("div");
  toastEl.className = `toast text-bg-${variant} border-0 mb-2`;
  toastEl.setAttribute("role", "alert");
  toastEl.setAttribute("aria-live", "assertive");
  toastEl.setAttribute("aria-atomic", "true");

  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        ${title ? `<div class="fw-semibold mb-1">${title}</div>` : ``}
        <div>${String(message ?? "")}</div>
      </div>
      <button type="button"
              class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast"
              aria-label="Close"></button>
    </div>
  `;

  container.appendChild(toastEl);

  const toast = bootstrap.Toast.getOrCreateInstance(toastEl, {
    delay: Number(delay) || 2000,
    autohide: true,
  });

  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
  toast.show();
}

// Global bridge for classic scripts
window.CartAPI = window.CartAPI || {};
window.CartAPI.getCart = getCart;
window.CartAPI.addToCart = addToCart;
window.CartAPI.setItemQuantity = setItemQuantity;
window.CartAPI.removeItem = removeItem;
window.CartAPI.getCartBadgeCount = getCartBadgeCount;
window.CartAPI.showToast = showToast;
