let selectedProductId = null;

// Pagination variables
let currentPage = 1;
const rowsPerPage = 10;

// ─── 1. Filter + Pagination ───────────────────────────────────────────────────

function applyAllFilters(resetPage = true) {
    if (resetPage) currentPage = 1;

    const nameSearch = document.getElementById('filterProductName').value.toLowerCase();
    const categorySearch = document.getElementById('filterCategory').value.toLowerCase();

    const checkedAvail = Array.from(
        document.querySelectorAll('.avail-filter:checked')
    ).map(cb => cb.value);

    const checkedStatus = Array.from(
        document.querySelectorAll('.status-filter:checked')
    ).map(cb => cb.value);

    const matchingRows = [];

    document.querySelectorAll('.order-row').forEach(row => {
        const avail       = row.getAttribute('data-availability');
        const status      = row.getAttribute('data-status');
        const productName = row.getAttribute('data-product-name');
        const category    = row.getAttribute('data-category');

        const availMatch    = checkedAvail.includes(avail);
        const statusMatch   = checkedStatus.includes(status);
        const nameMatch     = productName.includes(nameSearch);
        const catMatch      = categorySearch === '' || category === categorySearch;

        if (availMatch && statusMatch && nameMatch && catMatch) {
            matchingRows.push(row);
        } else {
            row.style.display = 'none';
        }
    });

    // Pagination
    const totalRows  = matchingRows.length;
    const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

    if (currentPage > totalPages) currentPage = totalPages;

    const startIndex = (currentPage - 1) * rowsPerPage;
    const endIndex   = startIndex + rowsPerPage;

    matchingRows.forEach((row, index) => {
        row.style.display = (index >= startIndex && index < endIndex) ? '' : 'none';
    });

    // Empty state row
    const emptyRow = document.getElementById('emptyStateRow');
    if (emptyRow) {
        emptyRow.style.display = totalRows === 0 ? '' : 'none';
    }

    renderPagination(totalPages);
    resetSelectionUI();
}

// ─── 2. Render Pagination Buttons ─────────────────────────────────────────────

function renderPagination(totalPages) {
    const container = document.getElementById('paginationContainer');
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '<ul class="pagination mb-0 shadow-sm">';

    html += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <button class="page-link" onclick="goToPage(${currentPage - 1})" style="color: var(--brand);">Previous</button>
             </li>`;

    for (let i = 1; i <= totalPages; i++) {
        const activeStyle = currentPage === i
            ? 'background-color: #3a4b53; border-color: #3a4b53; color: #fff;'
            : 'color: var(--brand);';
        html += `<li class="page-item ${currentPage === i ? 'active' : ''}">
                    <button class="page-link" onclick="goToPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
    }

    html += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <button class="page-link" onclick="goToPage(${currentPage + 1})" style="color: var(--brand);">Next</button>
             </li>`;

    html += '</ul>';
    container.innerHTML = html;
}

// ─── 3. Page Navigation ───────────────────────────────────────────────────────

function goToPage(pageNumber) {
    currentPage = pageNumber;
    applyAllFilters(false);
}

// ─── 4. Clear Filters ─────────────────────────────────────────────────────────

function clearFilters() {
    document.getElementById('filterProductName').value = '';
    document.getElementById('filterCategory').value = '';

    document.getElementById('filterAV').checked = true;
    document.getElementById('filterOOS').checked = true;
    document.getElementById('filterDIS').checked = false;
    document.getElementById('filterPUB').checked = true;
    document.getElementById('filterHID').checked = true;
    document.getElementById('filterFLG').checked = false;
    document.getElementById('filterRMV').checked = false;

    applyAllFilters(true);
}

// ─── 5. Select Row & Show Details ─────────────────────────────────────────────

function showProductDetails(productId, rowElement) {
    selectedProductId = productId;

    document.querySelectorAll('.order-row').forEach(r => r.classList.remove('selected'));
    rowElement.classList.add('selected');

    const productName = rowElement.getAttribute('data-edit-name');
    document.getElementById('detailProductName').textContent = productName;

    const template = document.getElementById(`details-template-${productId}`);
    if (template) {
        document.getElementById('detailsContent').innerHTML = template.innerHTML;
    }

    document.getElementById('editProductBtn').disabled = false;
    document.getElementById('cancelProductBtn').disabled = false;
}

// ─── 6. Reset Selection UI ────────────────────────────────────────────────────

function resetSelectionUI() {
    selectedProductId = null;
    document.querySelectorAll('.order-row').forEach(r => r.classList.remove('selected'));

    document.getElementById('detailProductName').textContent = 'Select a product';
    document.getElementById('detailsContent').innerHTML =
        '<p class="text-muted mb-0">Click on a product row above to view its full details including description, allergens, and inventory batches.</p>';

    document.getElementById('editProductBtn').disabled = true;
    document.getElementById('cancelProductBtn').disabled = true;
}

// ─── 7. Open Edit Modal ───────────────────────────────────────────────────────

function openEditModal() {
    if (!selectedProductId) return;

    const row = document.getElementById(`row-${selectedProductId}`);
    if (!row) return;

    document.getElementById('editName').value        = row.getAttribute('data-edit-name') || '';
    document.getElementById('editPrice').value       = row.getAttribute('data-edit-price') || '';
    document.getElementById('editUnit').value        = row.getAttribute('data-edit-unit') || '';
    document.getElementById('editCategory').value    = row.getAttribute('data-edit-category-id') || '';
    document.getElementById('editAvailability').value = row.getAttribute('data-edit-availability') || 'AV';
    document.getElementById('editOrganic').value     = row.getAttribute('data-edit-organic') || 'NOT_CERTIFIED';
    document.getElementById('editDescription').value = row.getAttribute('data-edit-description') || '';
    document.getElementById('editWholesalePrice').value = row.getAttribute('data-edit-wholesale-price') || '';

    // Clear any previous alert
    const alert = document.getElementById('editFormAlert');
    alert.className = 'alert mt-3 d-none';
    alert.textContent = '';

    const modal = new bootstrap.Modal(document.getElementById('editProductModal'));
    modal.show();
}

function updateDetailsTemplateAfterEdit(productId, data) {
    const template = document.getElementById(`details-template-${productId}`);
    if (!template) return;

    const content = template.content;
    const setText = (selector, value) => {
        const el = content.querySelector(selector);
        if (el) el.textContent = value;
    };

    const organicSelect = document.getElementById('editOrganic');
    const organicDisplay = organicSelect
        ? organicSelect.options[organicSelect.selectedIndex].text
        : '';

    const priceText = `£${parseFloat(data.price).toFixed(2)} per ${data.unit_display}`;
    const wholesaleText = data.wholesale_price
        ? `£${parseFloat(data.wholesale_price).toFixed(2)} per ${data.unit_display}`
        : 'Not set';
    const descriptionText = data.description && data.description.trim()
        ? data.description
        : 'No description provided.';

    setText('.js-detail-name', data.name);
    setText('.js-detail-category', data.category);
    setText('.js-detail-price', priceText);
    setText('.js-detail-wholesale', wholesaleText);
    if (organicDisplay) setText('.js-detail-organic', organicDisplay);
    setText('.js-detail-description', descriptionText);
}

// ─── 8. Submit Edit Form (AJAX) ───────────────────────────────────────────────

async function submitEditForm() {
    if (!selectedProductId) return;

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const alertEl   = document.getElementById('editFormAlert');

    const payload = {
        name:                        document.getElementById('editName').value.trim(),
        price:                       document.getElementById('editPrice').value,
        unit:                        document.getElementById('editUnit').value,
        category_id:                 document.getElementById('editCategory').value,
        availability_status:         document.getElementById('editAvailability').value,
        organic_certification_status: document.getElementById('editOrganic').value,
        description:                 document.getElementById('editDescription').value,
        wholesale_price:             document.getElementById('editWholesalePrice').value.trim(),
    };

    if (!payload.name) {
        alertEl.className = 'alert alert-danger mt-3';
        alertEl.textContent = 'Product name is required.';
        return;
    }

    if (payload.wholesale_price) {
        const basePrice = parseFloat(payload.price);
        const wholesalePrice = parseFloat(payload.wholesale_price);

        if (!Number.isNaN(basePrice) && !Number.isNaN(wholesalePrice) && wholesalePrice > basePrice) {
            alertEl.className = 'alert alert-danger mt-3';
            alertEl.textContent = 'Wholesale price cannot be higher than the base price.';
            return;
        }
    }

    document.getElementById('saveEditBtn').disabled = true;

    try {
        const response = await fetch(`/producer/products/${selectedProductId}/edit/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (data.success) {
            const editedProductId = selectedProductId;
            // Update row data attributes
            const row = document.getElementById(`row-${editedProductId}`);
            row.setAttribute('data-edit-name',          data.name);
            row.setAttribute('data-edit-price',         data.price);
            row.setAttribute('data-edit-unit',          data.unit);
            row.setAttribute('data-edit-category-id',   String(data.category_id));
            row.setAttribute('data-edit-availability',  data.availability_status);
            row.setAttribute('data-edit-organic',       data.organic_certification_status);
            row.setAttribute('data-edit-description',   data.description);
            row.setAttribute('data-edit-wholesale-price', data.wholesale_price || '');
            row.setAttribute('data-product-name',       data.name.toLowerCase());
            row.setAttribute('data-category',           data.category.toLowerCase());
            row.setAttribute('data-availability',       data.availability_status);

            // Update visible cells (0=ID, 1=Name, 2=Category, 3=Price, 4=Unit, 5=Stock, 6=Avail, 7=Status, 8=Date)
            row.cells[1].textContent = data.name;
            row.cells[2].textContent = data.category;
            row.cells[3].textContent = '£' + parseFloat(data.price).toFixed(2);
            row.cells[4].textContent = data.unit_display;

            // Update availability badge
            const availBadge = row.cells[6].querySelector('.status-badge');
            if (availBadge) {
                availBadge.textContent = data.availability_display;
                availBadge.className = `status-badge avail-${data.availability_status.toLowerCase()}`;
            }

            updateDetailsTemplateAfterEdit(editedProductId, data);

            // Update detail panel name
            document.getElementById('detailProductName').textContent = data.name;

            bootstrap.Modal.getInstance(document.getElementById('editProductModal')).hide();
            applyAllFilters(false);

            if (row.style.display !== 'none') {
                showProductDetails(editedProductId, row);
            }
        } else {
            alertEl.className = 'alert alert-danger mt-3';
            alertEl.textContent = data.error || 'An error occurred. Please try again.';
        }
    } catch (err) {
        console.error('Edit error:', err);
        alertEl.className = 'alert alert-danger mt-3';
        alertEl.textContent = 'Network error. Please try again.';
    } finally {
        document.getElementById('saveEditBtn').disabled = false;
    }
}

// ─── 9. Open Cancel Modal ─────────────────────────────────────────────────────

function openCancelModal() {
    if (!selectedProductId) return;

    const row = document.getElementById(`row-${selectedProductId}`);
    const productName = row ? row.getAttribute('data-edit-name') : 'this product';
    document.getElementById('cancelProductName').textContent = productName;

    const modal = new bootstrap.Modal(document.getElementById('cancelProductModal'));
    modal.show();
}

// ─── 10. Confirm Cancel (AJAX) ────────────────────────────────────────────────

async function confirmCancelProduct() {
    if (!selectedProductId) return;

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    try {
        const response = await fetch(`/producer/products/${selectedProductId}/cancel/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.success) {
            const row = document.getElementById(`row-${selectedProductId}`);
            if (row) {
                row.setAttribute('data-availability', data.availability_status);
                row.setAttribute('data-edit-availability', data.availability_status);

                const availBadge = row.cells[6].querySelector('.status-badge');
                if (availBadge) {
                    availBadge.textContent = data.availability_display;
                    availBadge.className = `status-badge avail-${data.availability_status.toLowerCase()}`;
                }
            }

            bootstrap.Modal.getInstance(document.getElementById('cancelProductModal')).hide();
            applyAllFilters(false);
        } else {
            alert('Something went wrong. Please try again.');
        }
    } catch (err) {
        console.error('Cancel error:', err);
        alert('Network error. Please try again.');
    }
}

// ─── Event Listeners ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Live-filter on any filter change
    document.querySelectorAll('.avail-filter, .status-filter').forEach(cb => {
        cb.addEventListener('change', () => applyAllFilters(true));
    });
    document.getElementById('filterProductName').addEventListener('input', () => applyAllFilters(true));
    document.getElementById('filterCategory').addEventListener('change', () => applyAllFilters(true));

    // Run initial filter to apply defaults (hides DIS/FLG/RMV on load)
    applyAllFilters(true);
});
