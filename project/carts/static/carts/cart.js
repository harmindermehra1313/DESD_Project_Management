// carts/static/carts/cart.js


const API_ROOT = "/api";
const M = window.CartApiMessages;

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
    if (!csrf) {
      throw new Error(M.csrfMissing);
    }
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
    const fallback = M.requestFailed(res.status);
    const msg = window.AppApiErrors.fromPayload(data, fallback);
    const err = new Error(msg);
    err.status = res.status;
    err.payload = data;
    throw err;
  }

  return { res, data };
}

export async function getCart() {
  const { data } = await request("GET", "/cart/");
  return data;
}

export async function addToCart({ inventoryId, quantity = 1 } = {}) {

  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error(M.invalidInventoryId);
  }

  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 1) {
    throw new Error(M.invalidQuantity);
  }

  const payload = { inventory_id: inventoryId, quantity: q };

  const { data } = await request("POST", "/cart/items/", {
    body: payload,
  });

  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "add" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return data;
}

export async function setItemQuantity({ inventoryId, quantity } = {}) {
  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error(M.invalidInventoryId);
  }

  const q = Number(quantity);
  if (!Number.isFinite(q) || q < 0) {
    throw new Error(M.invalidQuantity);
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

export async function removeItem({ inventoryId } = {}) {
  if (!Number.isInteger(inventoryId) || inventoryId <= 0) {
    throw new Error(M.invalidInventoryId);
  }

  await request("DELETE", `/cart/items/${inventoryId}/`);
  document.dispatchEvent(
    new CustomEvent("cart:updated", { detail: { action: "remove" } }),
  );
  await getCartBadgeCount().catch(() => {});
  return { ok: true };
}

export async function getCartBadgeCount() {
  const badge = document.getElementById("cartCount");
  if (!badge) return 0;

  badge.textContent = "0";
  badge.classList.remove("is-hidden");

  const cart = await getCart();
  const count = Number(cart?.total_quantity ?? 0);

  badge.textContent = String(count);
  badge.classList.remove("is-hidden");

  return count;
}

document.addEventListener("DOMContentLoaded", () => {
  getCartBadgeCount().catch(() => {});
});
document.addEventListener("cart:updated", () => {
  getCartBadgeCount().catch(() => {});
});

function ensureToastContainer() {
  const el = document.getElementById("toast-container");
  if (!el) {
    throw new Error(M.toastContainerMissing);
  }
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
              aria-label="${M.toastCloseLabel}"></button>
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

window.CartAPI = window.CartAPI || {};
window.CartAPI.getCart = getCart;
window.CartAPI.addToCart = addToCart;
window.CartAPI.setItemQuantity = setItemQuantity;
window.CartAPI.removeItem = removeItem;
window.CartAPI.getCartBadgeCount = getCartBadgeCount;
window.CartAPI.showToast = showToast;
