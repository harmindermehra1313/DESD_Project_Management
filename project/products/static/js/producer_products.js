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
    document.getElementById('filterPND').checked = true;

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
        //document.getElementById('detailsContent').innerHTML = template.innerHTML;
        const clone = template.content.cloneNode(true);
        document.getElementById('detailsContent').innerHTML = "";
        document.getElementById('detailsContent').appendChild(clone);
    }

    document.getElementById('editProductBtn').disabled = false;
    document.getElementById('cancelProductBtn').disabled = false;
    document.getElementById('batchProductBtn').disabled = false;
    setTimeout(() => toggleBatchVisibility(), 0);
}

// ─── 6. Reset Selection UI ────────────────────────────────────────────────────

function resetSelectionUI() {
    selectedProductId = null;
    document.querySelectorAll('.order-row').forEach(r => r.classList.remove('selected'));

    document.getElementById('detailProductName').textContent = 'Select a product';
    document.getElementById('detailsContent').innerHTML =
        '<p class="text-muted mb-0">Click on a product row above to view its full details including description, allergens, and inventory batches.</p>';

    document.getElementById('editProductBtn').disabled = true;
    document.getElementById('batchProductBtn').disabled = true;
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
    document.getElementById('editWholesaleMinQty').value = row.getAttribute('data-edit-wholesale-min-qty') || '';

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
        ? `£${parseFloat(data.wholesale_price).toFixed(2)} per ${data.unit_display} (min ${data.wholesale_min_quantity} units)`
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
        wholesale_min_quantity:      document.getElementById('editWholesaleMinQty').value.trim(),
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
        const response = await fetch(`/products/producer/products/${selectedProductId}/edit/`, {
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
            row.setAttribute('data-edit-wholesale-min-qty', data.wholesale_min_quantity || '');
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
            showGlobalSuccess("Product updated successfully!");

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

// ─── Open New Batch Modal ─────────────────────────────────────────────────────

function openBatchModal() {
    if (!selectedProductId) return;

    const today = new Date().toISOString().split("T")[0];
    const lastMonth = new Date();
    lastMonth.setDate(lastMonth.getDate() - 30);
    const lastMonthStr = lastMonth.toISOString().split("T")[0];

    const harvestInput = document.getElementById('batchHarvest');
    harvestInput.max = today;
    harvestInput.min = lastMonthStr;

    const expiryInput = document.getElementById('batchExpiry');
    expiryInput.min = today;
    expiryInput.max = "";

    // Reset form
    const form = document.getElementById('batchProductForm');
    form.reset();

    // Clear validation states
    form.querySelectorAll('.form-control').forEach(el => {
        el.classList.remove('is-invalid', 'is-valid');
    });

    // Clear alert
    const alert = document.getElementById('batchFormAlert');
    alert.className = 'alert mt-3 d-none';
    alert.textContent = '';

    const modal = new bootstrap.Modal(document.getElementById('batchProductModal'));
    modal.show();
}

function clearBatchAlert() {
    const alert = document.getElementById('batchFormAlert');
    alert.className = 'alert mt-3 d-none';
    alert.textContent = '';
}

// ─── Submit New Batch ────────────────────────────────────────────────────

function validateBatchForm() {
    let valid = true;

    const qty = document.getElementById('batchQuantity');
    const harvest = document.getElementById('batchHarvest');
    const expiry = document.getElementById('batchExpiry');

    const qtyVal = parseInt(qty.value);
    const harvestVal = harvest.value;
    const expiryVal = expiry.value;

    const today = new Date().toISOString().split("T")[0];
    const lastMonth = new Date();
    lastMonth.setDate(lastMonth.getDate() - 30);
    const lastMonthStr = lastMonth.toISOString().split("T")[0];

    // Quantity
    if (!qtyVal || qtyVal < 1 || qtyVal > 9999) {
        qty.classList.add("is-invalid");
        qty.classList.remove("is-valid");
        valid = false;
    } else {
        qty.classList.remove("is-invalid");
        qty.classList.add("is-valid");
    }

    // Harvest date
    if (!harvestVal || harvestVal > today || harvestVal < lastMonthStr) {
        harvest.classList.add("is-invalid");
        harvest.classList.remove("is-valid");
        valid = false;
    } else {
        harvest.classList.remove("is-invalid");
        harvest.classList.add("is-valid");
    }

    // Expiry date
    if (!expiryVal || expiryVal < today || expiryVal < harvestVal) {
        expiry.classList.add("is-invalid");
        expiry.classList.remove("is-valid");
        valid = false;
    } else {
        expiry.classList.remove("is-invalid");
        expiry.classList.add("is-valid");
    }

    return valid;
}

async function submitBatchForm() {
    if (!selectedProductId) return;

    if (!validateBatchForm()) {
        return; // stop submission
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const alertEl   = document.getElementById('batchFormAlert');

    const payload = {
        original_quantity: document.getElementById('batchQuantity').value,
        harvest_date:      document.getElementById('batchHarvest').value,
        expiry_date:       document.getElementById('batchExpiry').value,
        expiry_type:       document.querySelector('input[name="expiry_type"]:checked').value,
    };

    document.getElementById('saveBatchBtn').disabled = true;

    try {
        const response = await fetch(`/products/producer/products/${selectedProductId}/add-batch/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (data.success) {
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('batchProductModal')).hide();

            // Refresh details panel (inventory list)
            const template = document.getElementById(`details-template-${selectedProductId}`);
            if (data.batch) {
                insertNewBatchIntoUI(data.batch);
                sortBatchItems();
                sortHiddenTemplateBatches();
                toggleBatchVisibility();
                //showProductDetails(selectedProductId, document.getElementById(`row-${selectedProductId}`));
            }

            showGlobalSuccess("New batch added successfully!");
            
            // Update stock cell in main table
            const row2 = document.getElementById(`row-${selectedProductId}`);
            if (row2 && data.total_stock !== undefined) {
                row2.cells[5].textContent = data.total_stock; // column 5 = stock
            }

            // Reapply filters and keep selection
            applyAllFilters(false);

        } else {
            alertEl.className = 'alert alert-danger mt-3';
            alertEl.textContent = data.error || 'An error occurred. Please try again.';
        }

    } catch (err) {
        console.error('Batch error:', err);
        alertEl.className = 'alert alert-danger mt-3';
        alertEl.textContent = 'Network error. Please try again.';
    } finally {
        document.getElementById('saveBatchBtn').disabled = false;
    }
}

function sortHiddenTemplateBatches() {
    const hiddenTemplate = document.querySelector(`#details-template-${selectedProductId}`);
    if (!hiddenTemplate) return;

    const container = hiddenTemplate.content.querySelector('#batchItemsContainer');
    if (!container) return;

    const items = Array.from(container.querySelectorAll('.batch-item'));

    items.sort((a, b) => {
        const dateA = new Date(a.getAttribute('data-expiry'));
        const dateB = new Date(b.getAttribute('data-expiry'));
        return dateA - dateB;
    });

    container.innerHTML = "";
    items.forEach(item => container.appendChild(item));
}

function insertNewBatchIntoUI(batch) {
    const container = document.querySelector('#detailsContent #batchItemsContainer');
    if (!container) return;

    // Always convert to ISO for sorting
    const isoExpiry = new Date(batch.expiry_date).toISOString().split("T")[0];
    const formattedExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB");

    const li = document.createElement('li');
    li.className = "d-flex justify-content-between align-items-center mb-1 batch-item";
    li.setAttribute("data-batch-id", batch.id);
    li.setAttribute("data-remaining", batch.remaining_quantity);
    li.setAttribute("data-expiry", isoExpiry);
    li.setAttribute("data-batch-status", "active");

    li.innerHTML = `
        <div>
            <span class="text-muted small">Stock:</span>
            ${batch.remaining_quantity} / ${batch.remaining_quantity} -
            <span class="text-muted small">${batch.expiry_type === "BB" ? "Best Before" : "Use By"}:</span>
            ${formattedExpiry}
        </div>

        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary"
                    onclick="openReduceBatchModal(${batch.id})"
                    ${batch.remaining_quantity == 0 ? "disabled" : ""}>
                Reduce Stock
            </button>

            <button class="btn btn-outline-danger"
                    onclick="openDeleteBatchModal(${batch.id})">
                Delete Batch
            </button>
        </div>
    `;

    // Insert into visible container
    container.appendChild(li);

    // Insert into hidden template BEFORE sorting
    const hiddenTemplate = document.querySelector(`#details-template-${selectedProductId}`);
    if (hiddenTemplate) {
        const hiddenContainer = hiddenTemplate.content.querySelector('#batchItemsContainer');
        if (hiddenContainer) {
            hiddenContainer.appendChild(li.cloneNode(true));
        }
    }

    // Sort after both containers are updated
    sortBatchItems();
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
        const response = await fetch(`/products/producer/products/${selectedProductId}/cancel/`, {
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

// ─── Reduce and delete batches ──────────────────────────────────────────────────────────

let selectedBatchId = null;

function openReduceBatchModal(batchId) {
    selectedBatchId = batchId;

    const batchEl = document.querySelector(`[data-batch-id="${batchId}"]`);
    const remaining = parseInt(batchEl.getAttribute("data-remaining"));

    document.getElementById("reduceAmount").setAttribute("max", remaining);
    document.getElementById("reduceAmount").setAttribute("min", 1);

    document.getElementById("reduceAmount").value = "";

    document.getElementById("reduceBatchRange").textContent =
        `Enter a number between 1 and ${remaining}`;

    new bootstrap.Modal(document.getElementById('reduceBatchModal')).show();
}


function openDeleteBatchModal(batchId) {
    selectedBatchId = batchId;
    new bootstrap.Modal(document.getElementById('deleteBatchModal')).show();
}

async function submitReduceBatch() {
    const amountInput = document.getElementById('reduceAmount');
    const alertEl = document.getElementById('reduceBatchAlert');
    const amount = parseInt(amountInput.value);

    alertEl.classList.add("d-none");
    const max = parseInt(amountInput.getAttribute("max"));

    if (!amount || amount < 1 || amount > max) {
        alertEl.textContent = `Enter a number between 1 and ${max}.`;
        alertEl.classList.remove("d-none");
        amountInput.classList.add("is-invalid");
        return;
    }

    amountInput.classList.remove("is-invalid");

    const response = await fetch(`/products/producer/products/${selectedProductId}/reduce-batch/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ batch_id: selectedBatchId, amount })
    });

    const data = await response.json();

    if (!data.success) {
        alertEl.textContent = data.error;
        alertEl.classList.remove("d-none");
        amountInput.classList.add("is-invalid");
        return;
    }

    bootstrap.Modal.getInstance(document.getElementById('reduceBatchModal')).hide();
    showGlobalSuccess("Batch reduced successfully.");
    updateBatchUI(data);
    sortBatchItems();
}

async function submitDeleteBatch() {
    const response = await fetch(`/products/producer/products/${selectedProductId}/delete-batch/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ batch_id: selectedBatchId })
    });

    const data = await response.json();

    if (data.success) {
        updateBatchUI(data);
        bootstrap.Modal.getInstance(document.getElementById('deleteBatchModal')).hide();
        showGlobalSuccess("Batch deleted.");
        sortBatchItems();
    }
}

function sortBatchItems() {
    const container = document.querySelector('#detailsContent #batchItemsContainer');
    if (!container) return;

    const items = Array.from(container.querySelectorAll('.batch-item'));

    items.sort((a, b) => {
        const dateA = new Date(a.getAttribute('data-expiry'));
        const dateB = new Date(b.getAttribute('data-expiry'));
        return dateA - dateB;
    });

    container.innerHTML = "";
    items.forEach(item => container.appendChild(item));
}

function updateBatchUI(data) {
    // Update stock in main table
    const row = document.getElementById(`row-${selectedProductId}`);
    if (row) row.cells[5].textContent = data.total_stock;

    // Update hidden template
    const template = document.getElementById(`details-template-${selectedProductId}`);
    const hiddenContainer = template.content.querySelector('#batchItemsContainer');
    hiddenContainer.innerHTML = data.updated_batches_html;

    // Update visible details panel
    const visibleContainer = document.querySelector('#detailsContent #batchItemsContainer');
    if (visibleContainer) {
        visibleContainer.innerHTML = data.updated_batches_html;
    }

    // Extract deleted batches
    // const newDeleted = temp.querySelector("#deletedItemsContainer");
    // const deletedContainer = document.querySelector("#detailsContent #deletedItemsContainer");
    // if (newDeleted && deletedContainer) {
    //     deletedContainer.innerHTML = newDeleted.innerHTML;
    // }

    // Re-run visibility logic
    toggleBatchVisibility();
}

function toggleBatchVisibility() {
    const showExpired = document.getElementById("toggleExpired").checked;
    const showDeleted = document.getElementById("toggleDeleted").checked;

    const expiredItems = document.querySelectorAll('#detailsContent .batch-item[data-batch-status="expired"]');
    const deletedItems = document.querySelectorAll('#detailsContent .batch-item[data-batch-status="deleted"]');

    // Toggle expired visibility
    expiredItems.forEach(item => {
        item.style.display = showExpired ? "" : "none";
    });

    // Toggle deleted visibility
    deletedItems.forEach(item => {
        item.style.display = showDeleted ? "" : "none";
    });

    // Count visible expired items
    const visibleExpired = Array.from(expiredItems).filter(
        item => item.style.display !== "none"
    ).length;

    // Count visible deleted items
    const visibleDeleted = Array.from(deletedItems).filter(
        item => item.style.display !== "none"
    ).length;

    // Show/hide small-print messages
    // Only show if checkbox is ON AND no visible items
    document.getElementById("noExpiredMsg").classList.toggle(
        "d-none",
        !showExpired || visibleExpired !== 0
    );

    document.getElementById("noDeletedMsg").classList.toggle(
        "d-none",
        !showDeleted || visibleDeleted !== 0
    );
}

// ─── Event Listeners ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Live-filter on any filter change
    document.querySelectorAll('.avail-filter, .status-filter').forEach(cb => {
        cb.addEventListener('change', () => applyAllFilters(true));
    });
    document.getElementById('filterProductName').addEventListener('input', () => applyAllFilters(true));
    document.getElementById('filterCategory').addEventListener('change', () => applyAllFilters(true));

    document.getElementById('batchHarvest').addEventListener('change', () => {
        const harvest = document.getElementById('batchHarvest').value;
        const expiry = document.getElementById('batchExpiry');
        const today = new Date().toISOString().split("T")[0];

        // expiry must be >= both today and harvest
        expiry.min = harvest > today ? harvest : today;

        validateBatchForm();
        clearBatchAlert();
    });

    document.getElementById('batchExpiry').addEventListener('change', () => {
        validateBatchForm();
        clearBatchAlert();
    });

    document.getElementById('batchQuantity').addEventListener('input', () => {
        validateBatchForm();
        clearBatchAlert();
    });

    document.addEventListener("change", (e) => {
        if (e.target.id === "toggleExpired" || e.target.id === "toggleDeleted") {
            toggleBatchVisibility();
        }
    });

    // Run initial filter to apply defaults (hides DIS/FLG/RMV on load)
    applyAllFilters(true);
});

function showGlobalSuccess(message) {
    const alert = document.getElementById('globalSuccessAlert');
    alert.textContent = message;
    alert.classList.remove('d-none');

    // Auto-hide after 30 seconds
    setTimeout(() => {
        alert.classList.add('d-none');
    }, 30000);
}
