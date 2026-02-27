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

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.error)) ||
      `Request failed (HTTP ${res.status})`;
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
export async function addToCart({ productId, quantity = 1 } = {}) {
  if (!Number.isInteger(productId) || productId <= 0) {
    throw new Error("addToCart: productId must be a positive integer");
  }
  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 1) {
    throw new Error("addToCart: quantity must be >= 1");
  }

  const { data } = await request("POST", "/cart/items/", {
    body: { product_id: productId, quantity: q },
  });

  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "add" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return data;
}

/** PATCH /api/cart/items/<product_id>/ */
export async function setItemQuantity({ productId, quantity } = {}) {
  if (!Number.isInteger(productId) || productId <= 0) {
    throw new Error("setItemQuantity: productId must be a positive integer");
  }
  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 0) {
    throw new Error("setItemQuantity: quantity must be >= 0");
  }

  const { res, data } = await request("PATCH", `/cart/items/${productId}/`, {
    body: { quantity: q },
  });

  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "set_qty" } }),
  );
  await getCartBadgeCount().catch(() => {});
  if (res.status === 204) return null;
  return data;
}

/** DELETE /api/cart/items/<product_id>/ */
export async function removeItem({ productId } = {}) {
  if (!Number.isInteger(productId) || productId <= 0) {
    throw new Error("removeItem: productId must be a positive integer");
  }

  await request("DELETE", `/cart/items/${productId}/`);
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

  const cart = await getCart();
  const count = Number(cart?.total_quantity ?? 0);

  badge.textContent = String(count);
  badge.classList.toggle("is-hidden", count <= 0);

  return count;
}

// Init badge on every page load + keep in sync
document.addEventListener("DOMContentLoaded", () => {
  getCartBadgeCount().catch(() => {});
});
document.addEventListener("cart:updated", () => {
  getCartBadgeCount().catch(() => {});
});

// Global bridge for classic scripts
window.CartAPI = window.CartAPI || {};
window.CartAPI.getCart = getCart;
window.CartAPI.addToCart = addToCart;
window.CartAPI.setItemQuantity = setItemQuantity;
window.CartAPI.removeItem = removeItem;
window.CartAPI.getCartBadgeCount = getCartBadgeCount;
