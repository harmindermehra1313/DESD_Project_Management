(() => {
  const cfg = document.getElementById("productConfig");
  const productId = cfg.dataset.productId;
  const PRODUCT_API_BASE = cfg.dataset.productApiBase || "/api/products/";
  const CART_BASE_CANDIDATES = [cfg.dataset.cartBase || "/api/cart/", "/api/carts/"]; // just in case

  const els = {
    alert: document.getElementById("alert"),
    img: document.getElementById("pImage"),
    name: document.getElementById("pName"),
    farm: document.getElementById("pFarm"),
    category: document.getElementById("pCategory"),
    desc: document.getElementById("pDesc"),
    price: document.getElementById("pPrice"),
    unit: document.getElementById("pUnit"),
    total: document.getElementById("pTotal"),
    qty: document.getElementById("qty"),
    add: document.getElementById("addToCart"),
    allergens: document.getElementById("pAllergens"),
    wholesale: document.getElementById("pWholesale"),
  };

  const fmtGBP = (n) =>
    new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(n);

  function setAlert(kind, msg) {
    els.alert.innerHTML = `<div class="alert alert-${kind}">${msg}</div>`;
  }

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const c of cookies) {
      const v = c.trim();
      if (v.startsWith(name + "=")) return decodeURIComponent(v.slice(name.length + 1));
    }
    return null;
  }

  // Django recommends using the csrftoken cookie as the canonical token source for AJAX POSTs
  // (requires CSRF middleware enabled).
  const csrfToken = () => getCookie("csrftoken");

  function imageUrl(product) {
    const img = (product.image || "").trim();
    if (!img) return "/static/img/placeholder-product.png";
    if (img.startsWith("http") || img.startsWith("/")) return img;
    return `/media/${img}`; // common Django media pattern; adjust if you store differently
  }

  let product = null;

  function recalcTotal() {
    if (!product) return;
    const qty = Math.max(1, parseInt(els.qty.value || "1", 10));
    els.qty.value = String(qty);

    const unitPrice = parseFloat(product.price);
    if (Number.isFinite(unitPrice)) {
      els.total.textContent = fmtGBP(unitPrice * qty);
    } else {
      els.total.textContent = "£—";
    }
  }

  function render(p) {
    els.img.src = imageUrl(p);
    els.img.alt = p.name || "Product image";

    els.name.textContent = p.name || "Unnamed product";
    els.farm.textContent = p.producer?.farm_name || p.farm_origin || "";
    els.category.textContent = p.category?.name || "";

    els.desc.textContent = p.description || "";

    const unitPrice = parseFloat(p.price);
    els.price.textContent = Number.isFinite(unitPrice) ? fmtGBP(unitPrice) : "£—";
    els.unit.textContent = (p.unit || "").toLowerCase();

    // Allergens
    els.allergens.innerHTML = "";
    const allergenItems = (p.allergens || []).map(x => x.allergen?.name).filter(Boolean);
    if (!allergenItems.length) {
      els.allergens.innerHTML = `<li class="text-muted">No allergens listed</li>`;
    } else {
      for (const a of allergenItems) {
        const li = document.createElement("li");
        li.textContent = a;
        els.allergens.appendChild(li);
      }
    }

    const tiers = p.wholesale_prices || [];
    if (!tiers.length) {
      els.wholesale.textContent = "No wholesale tiers.";
    } else {
      els.wholesale.innerHTML = `
        <ul class="mb-0">
          ${tiers.map(t => `<li>${JSON.stringify(t)}</li>`).join("")}
        </ul>
      `;
    }

    recalcTotal();
  }

  async function fetchProduct() {
    setAlert("info", "Loading product…");

    const r = await fetch(`${PRODUCT_API_BASE}${productId}/`, {
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
    });

    if (!r.ok) {
      setAlert("danger", `Failed to load product (HTTP ${r.status}).`);
      return;
    }

    product = await r.json();
    els.alert.innerHTML = "";
    render(product);
  }

  async function addToCart() {
    if (!product) return;

    const qty = Math.max(1, parseInt(els.qty.value || "1", 10));
    const payload = { product_id: product.id, quantity: qty };

    const ADD_PATH = "items/";

    let lastErr = null;

    for (const base of CART_BASE_CANDIDATES) {
      try {
        const url = `${base}${ADD_PATH}`;
        const r = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-CSRFToken": csrfToken() || "",
          },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });

        if (r.status === 401) {
          setAlert("warning", "You need to be logged in to add items to cart.");
          return;
        }

        if (!r.ok) {
          const text = await r.text().catch(() => "");
          lastErr = `HTTP ${r.status} from ${url}: ${text}`;
          continue;
        }
        const cart = await r.json();
        setAlert("success", "Added to cart!");
        if (window.BRFNCart) window.BRFNCart.setFromCart(cart);
        return;

      } catch (e) {
        lastErr = String(e);
      }
    }

    setAlert(
      "danger",
      `Add to cart failed. Check your cart endpoint.\n\nLast error: ${lastErr || "Unknown"}`
    );
  }

  els.qty.addEventListener("input", recalcTotal);
  els.add.addEventListener("click", addToCart);

  fetchProduct();
})();


