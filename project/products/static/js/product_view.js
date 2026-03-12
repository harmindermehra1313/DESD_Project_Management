// document.addEventListener("DOMContentLoaded", () => {

//     const products = JSON.parse(document.getElementById("productsData").textContent);
//     const showFilters = document.getElementById("showFiltersFlag").textContent.trim() === "true";

//     function formatPrice(value) {
//         return Number(value).toFixed(2);
//     }

//     function renderProducts(list) {
//         const grid = document.getElementById("productGrid");
//         grid.innerHTML = "";

//         if (list.length === 0) {
//             grid.innerHTML = "<p class='text-muted text-center mt-3'>No products found.</p>";
//             return;
//         }

//         list.forEach(p => {
//             const shortDesc = p.description
//                 ? p.description.substring(0, 60) + "..."
//                 : "No description available.";

//             grid.innerHTML += `
//                 <div class="col">
//                     <div class="card h-100 shadow-sm product-card">
//                         <div class="card-header bg-white text-center fw-bold border-0 pt-3">
//                             ${p.name}
//                         </div>

//                         <img src="${p.image}" class="card-img-top" alt="${p.name}" loading="lazy">

//                         <div class="card-body d-flex flex-column">
//                             <p class="text-muted small mb-2">By: ${p.producer}</p>
//                             <p class="card-text small mb-3">${shortDesc}</p>
//                             <h5 class="fw-bold mb-3 text-success">£${formatPrice(p.price)}</h5>

//                             <a href="/products/${p.id}/"
//                                class="btn btn-brand-outline w-100 mt-auto">
//                                 More Information
//                             </a>
//                         </div>
//                     </div>
//                 </div>
//             `;
//         });
//     }

//     function applyFilters() {
//         let list = [...products];

//         const search = document.getElementById("searchInput")?.value.toLowerCase() || "";
//         const minPrice = parseFloat(document.getElementById("minPrice")?.value);
//         const maxPrice = parseFloat(document.getElementById("maxPrice")?.value);
//         const sort = document.getElementById("sortSelect")?.value;

//         let category = "";
//         let producer = "";

//         if (showFilters) {
//             category = document.getElementById("categoryFilter")?.value || "";
//             producer = document.getElementById("producerFilter")?.value || "";
//         }

//         if (search) {
//             list = list.filter(p =>
//                 p.name.toLowerCase().includes(search) ||
//                 p.description.toLowerCase().includes(search) ||
//                 p.producer.toLowerCase().includes(search)
//             );
//         }

//         if (showFilters && category) list = list.filter(p => p.category === category);
//         if (showFilters && producer) list = list.filter(p => p.producer === producer);

//         if (!isNaN(minPrice)) list = list.filter(p => p.price >= minPrice);
//         if (!isNaN(maxPrice)) list = list.filter(p => p.price <= maxPrice);

//         if (sort === "price_low") list.sort((a, b) => a.price - b.price);
//         if (sort === "price_high") list.sort((a, b) => b.price - a.price);
//         if (sort === "newest") list.sort((a, b) => b.id - a.id);

//         renderProducts(list);
//     }

//     ["searchInput", "categoryFilter", "producerFilter", "minPrice", "maxPrice", "sortSelect"]
//         .forEach(id => {
//             const el = document.getElementById(id);
//             if (el) el.addEventListener("input", applyFilters);
//         });

//     renderProducts(products);
// });
document.addEventListener("DOMContentLoaded", () => {

    const products = JSON.parse(document.getElementById("productsData").textContent);
    const showFilters = document.getElementById("showFiltersFlag").textContent.trim() === "true";

    function formatPrice(value) {
        return Number(value).toFixed(2);
    }

    function renderProducts(list) {
        const grid = document.getElementById("productGrid");
        grid.innerHTML = "";

        if (list.length === 0) {
            grid.innerHTML = "<p class='text-muted text-center mt-3'>No products found.</p>";
            return;
        }

        list.forEach(p => {

            // -------------------------
            // BADGES
            // -------------------------
            let badges = "";

            if (p.organic) {
                badges += `<span class="badge bg-success me-1">Organic</span>`;
            }
            if (p.local) {
                badges += `<span class="badge bg-primary me-1">Local</span>`;
            }
            if (p.fresh_today) {
                badges += `<span class="badge bg-warning text-dark me-1">Fresh Today</span>`;
            }
            if (p.low_stock) {
                badges += `<span class="badge bg-danger me-1">Low Stock</span>`;
            }
            if (p.has_discount) {
                badges += `<span class="badge bg-danger me-1">Sale</span>`;
            }

            // -------------------------
            // PRICE DISPLAY (discount + original)
            // -------------------------
            let priceHTML = "";

            if (p.has_discount) {
                priceHTML = `
                    <div class="mb-3">
                        <span class="text-danger fw-bold">£${formatPrice(p.price)}</span>
                        <span class="text-muted text-decoration-line-through ms-2">
                            £${formatPrice(p.original_price)}
                        </span>
                        <span class="badge bg-danger ms-2">-${p.discount_percent}%</span>
                    </div>
                `;
            } else {
                priceHTML = `
                    <h5 class="fw-bold mb-3 text-success">£${formatPrice(p.price)}</h5>
                `;
            }

            // -------------------------
            // SHORT DESCRIPTION
            // -------------------------
            const shortDesc = p.description
                ? p.description.substring(0, 60) + "..."
                : "No description available.";

            // -------------------------
            // PRODUCT CARD
            // -------------------------
            grid.innerHTML += `
                <div class="col">
                    <div class="card h-100 shadow-sm product-card">

                        <div class="card-header bg-white text-center fw-bold border-0 pt-3">
                            ${p.name}
                        </div>

                        <img src="${p.image}" class="card-img-top" alt="${p.name}" loading="lazy">

                        <div class="card-body d-flex flex-column">

                            <div class="mb-2">${badges}</div>

                            <p class="text-muted small mb-2">By: ${p.producer}</p>
                            <p class="card-text small mb-3">${shortDesc}</p>

                            ${priceHTML}

                            <a href="/products/${p.id}/"
                               class="btn btn-brand-outline w-100 mt-auto">
                                More Information
                            </a>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    function applyFilters() {
        let list = [...products];

        const search = document.getElementById("searchInput")?.value.toLowerCase() || "";
        const minPrice = parseFloat(document.getElementById("minPrice")?.value);
        const maxPrice = parseFloat(document.getElementById("maxPrice")?.value);
        const sort = document.getElementById("sortSelect")?.value;

        let category = "";
        let producer = "";

        if (showFilters) {
            category = document.getElementById("categoryFilter")?.value || "";
            producer = document.getElementById("producerFilter")?.value || "";
        }

        if (search) {
            list = list.filter(p =>
                p.name.toLowerCase().includes(search) ||
                p.description.toLowerCase().includes(search) ||
                p.producer.toLowerCase().includes(search)
            );
        }

        if (showFilters && category) list = list.filter(p => p.category === category);
        if (showFilters && producer) list = list.filter(p => p.producer === producer);

        if (!isNaN(minPrice)) list = list.filter(p => p.price >= minPrice);
        if (!isNaN(maxPrice)) list = list.filter(p => p.price <= maxPrice);

        if (sort === "price_low") list.sort((a, b) => a.price - b.price);
        if (sort === "price_high") list.sort((a, b) => b.price - a.price);
        if (sort === "newest") list.sort((a, b) => b.id - a.id);

        renderProducts(list);
    }

    ["searchInput", "categoryFilter", "producerFilter", "minPrice", "maxPrice", "sortSelect"]
        .forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("input", applyFilters);
        });

    renderProducts(products);
});