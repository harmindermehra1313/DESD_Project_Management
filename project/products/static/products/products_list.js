document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("productsGrid");
  const msg = document.getElementById("productsMsg");
  const search = document.getElementById("productSearch");
  const sort = document.getElementById("productSort");

  let all = [];

  function show(text, type = "danger") {
    msg.innerHTML = `<div class="alert alert-${type}">${text}</div>`;
  }

  function clearMsg() {
    msg.innerHTML = "";
  }


  function resolveImageUrl(imageValue) {
    if (!imageValue) return null;
    if (imageValue.startsWith("http://") || imageValue.startsWith("https://")) return imageValue;
    if (imageValue.startsWith("/")) return imageValue;

    const candidates = [
      `/media/${imageValue}`,
      `/static/${imageValue}`,
      `/static/images/${imageValue}`,
      `/static/products/${imageValue}`,
    ];
    return candidates[0]; // render first; if it 404s, browser will show broken img (you can replace with placeholder later)
  }

  function fmtMoney(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(2) : "0.00";
  }

  function cardHTML(p) {
    const id = p.id;
    const name = p.name ?? "Unnamed";
    const price = fmtMoney(p.price);
    const unit = p.unit ?? "";
    const category = p.category?.name ?? "";
    const farm = p.producer?.farm_name ?? p.farm_origin ?? "";
    const availability = p.availability_status ?? "";
    const status = p.status ?? "";

    const imgUrl = resolveImageUrl(p.image);
    const img = imgUrl
      ? `<img src="${imgUrl}" class="card-img-top" alt="${name}" style="object-fit:cover;height:160px;">`
      : "";

    const badge = `
      <span class="badge text-bg-${availability === "AVAILABLE" ? "success" : "secondary"}">
        ${availability || "UNKNOWN"}
      </span>
      <span class="badge text-bg-${status === "PUBLISHED" ? "primary" : "secondary"} ms-1">
        ${status || "UNKNOWN"}
      </span>
    `;

    return `
      <div class="col-12 col-md-6 col-lg-4">
        <a class="text-decoration-none" href="/products/${id}/">
          <div class="card h-100">
            ${img}
            <div class="card-body">
              <div class="d-flex align-items-start justify-content-between gap-2">
                <div class="fw-semibold">${name}</div>
                <div class="text-nowrap">£${price} / ${unit}</div>
              </div>

              <div class="text-muted small mt-1">
                ${category ? `Category: ${category}` : ""}
                ${category && farm ? " · " : ""}
                ${farm ? `Farm: ${farm}` : ""}
              </div>

              <div class="mt-2">${badge}</div>
            </div>
          </div>
        </a>
      </div>
    `;
  }

  function applyFilterSort() {
    const q = (search.value || "").trim().toLowerCase();
    const sortMode = sort.value;

    let filtered = all;

    if (q) {
      filtered = all.filter(p => {
        const hay = [
          p.name,
          p.category?.name,
          p.producer?.farm_name,
          p.farm_origin,
          p.description,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return hay.includes(q);
      });
    }

    filtered = filtered.slice().sort((a, b) => {
      if (sortMode === "name") {
        return String(a.name || "").localeCompare(String(b.name || ""));
      }
      const pa = Number(a.price || 0);
      const pb = Number(b.price || 0);
      if (sortMode === "price_asc") return pa - pb;
      if (sortMode === "price_desc") return pb - pa;
      return 0;
    });

    if (!filtered.length) {
      grid.innerHTML = "";
      show("No products match your search.", "warning");
      return;
    }

    clearMsg();
    grid.innerHTML = filtered.map(cardHTML).join("");
  }

  async function load() {
    try {
      const resp = await fetch("/api/products/", { credentials: "include" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (!Array.isArray(data)) {
        throw new Error("Expected a list from /api/products/ (but got something else).");
      }

      all = data.filter(p => (p.status === "PUBLISHED") && (p.availability_status === "AVAILABLE"));

      if (!all.length) {
        show("No PUBLISHED + AVAILABLE products found.", "warning");
        return;
      }

      applyFilterSort();
    } catch (e) {
      show(`Failed to load products: ${e.message}`, "danger");
    }
  }

  search.addEventListener("input", applyFilterSort);
  sort.addEventListener("change", applyFilterSort);

  await load();
});