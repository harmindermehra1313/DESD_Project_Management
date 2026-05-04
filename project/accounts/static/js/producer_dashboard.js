let selectedSummaryId = null;

// Pagination variables
let currentPage = 1;
let subCurrentPage = 1;
const rowsPerPage = 10;

// 1. Evaluates ID, Name, Dates, Checkboxes, AND Pagination
function applyAllFilters(resetPage = true, resetDetails = true) {
    if (resetPage) {
        currentPage = 1;
    }

    // Get text/date filter values
    const orderIdSearch = document.getElementById('filterOrderId').value.toLowerCase();
    const nameSearch = document.getElementById('filterCustomerName').value.toLowerCase();
    const fromDate = document.getElementById('filterDateFrom').value;
    const toDate = document.getElementById('filterDateTo').value;
    
    // Gather an array of all the status codes that are currently checked
    const checkedStatuses = Array.from(document.querySelectorAll('.status-filter:checked')).map(cb => cb.value);
    
    let matchingRows = [];

    document.querySelectorAll('.order-row').forEach(row => {
        // Grab the row's hidden data attributes
        const status = row.getAttribute('data-status');
        const orderId = row.getAttribute('data-order-id');
        const customerName = row.getAttribute('data-customer-name');
        const dueDate = row.getAttribute('data-due-date');
        
        let statusMatch = checkedStatuses.includes(status);
        let orderIdMatch = orderId.includes(orderIdSearch);
        let nameMatch = customerName.includes(nameSearch);
        let fromMatch = true;
        let toMatch = true;
        
        if (fromDate !== "" && dueDate < fromDate) fromMatch = false;
        if (toDate !== "" && dueDate > toDate) toMatch = false;

        // If ALL conditions are met, save it to matching array
        if (statusMatch && orderIdMatch && nameMatch && fromMatch && toMatch) {
            matchingRows.push(row);
        } else {
            row.style.display = 'none'; // Hide immediately if it fails the filter
        }
    });

    // --- PAGINATION LOGIC ---
    const totalRows = matchingRows.length;
    const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

    if (currentPage > totalPages) {
        currentPage = totalPages;
    }

    const startIndex = (currentPage - 1) * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;

    matchingRows.forEach((row, index) => {
        if (index >= startIndex && index < endIndex) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    const emptyRow = document.getElementById('emptyStateRow');
    if (emptyRow) {
        emptyRow.style.display = totalRows === 0 ? '' : 'none';
    }

    renderPagination(totalPages);

    // --- RESET DETAILS PANEL ---
    if (resetDetails) {
        selectedSummaryId = null;
        document.querySelectorAll('.order-row').forEach(r => r.classList.remove('selected'));
        document.querySelectorAll('.sub-row').forEach(r => r.classList.remove('selected'));
        
        const detailOrderId = document.getElementById('detailOrderId');
        const detailsContent = document.getElementById('detailsContent');
        
        if (detailOrderId) detailOrderId.textContent = 'Select an order';
        if (detailsContent) {
            detailsContent.innerHTML = '<p class="text-muted mb-0">Click on a specific order or subscription from the tables above to view complete details.</p>';
        }
        
        const updateBtn = document.getElementById('updateStatusBtn');
        if (updateBtn) {
            updateBtn.disabled = true;
        }
    }
}

// 2. Render Pagination Buttons visually
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
        const activeClass = currentPage === i ? 'active' : '';
        const activeStyle = currentPage === i ? 'background-color: #3a4b53; border-color: #3a4b53; color: #fff;' : 'color: var(--brand);';
        
        html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="goToPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
    }

    html += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <button class="page-link" onclick="goToPage(${currentPage + 1})" style="color: var(--brand);">Next</button>
             </li>`;

    html += '</ul>';
    container.innerHTML = html;
}

// 3. Jump to a new page
function goToPage(pageNumber) {
    currentPage = pageNumber;
    applyAllFilters(false);
}

// 4. Clear all filters and reset view
function clearFilters() {
    document.getElementById('filterOrderId').value = '';
    document.getElementById('filterCustomerName').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    
    document.getElementById('filterPen').checked = true;
    document.getElementById('filterPre').checked = true;
    document.getElementById('filterPac').checked = true;
    document.getElementById('filterShp').checked = false;

    applyAllFilters(true); 
}

// 5. Highlight row and show details
function showOrderDetails(summaryId, rowElement) {
    selectedSummaryId = summaryId;

    document.querySelectorAll('.order-row').forEach(row => row.classList.remove('selected'));
    document.querySelectorAll('.sub-row').forEach(row => row.classList.remove('selected'));
    rowElement.classList.add('selected');

    const orderRef = rowElement.cells[0].innerText.split('\n')[0].trim();
    document.getElementById('detailOrderId').textContent = `Order ${orderRef}`;

    const templateContent = document.getElementById(`details-template-${summaryId}`).innerHTML;
    document.getElementById('detailsContent').innerHTML = templateContent;

    const updateBtn = document.getElementById('updateStatusBtn');
    if (updateBtn) updateBtn.disabled = false;
}

// 6. Show Subscription Details
function showSubscriptionDetails(subId, rowElement) {
    selectedSummaryId = null;

    document.querySelectorAll('.order-row').forEach(row => row.classList.remove('selected'));
    document.querySelectorAll('.sub-row').forEach(row => row.classList.remove('selected'));
    rowElement.classList.add('selected');

    document.getElementById('detailOrderId').textContent = `Subscription #SUB-${subId}`;

    const template = document.getElementById(`sub-details-template-${subId}`);
    if (template) {
        document.getElementById('detailsContent').innerHTML = template.innerHTML;
    }

    const updateBtn = document.getElementById('updateStatusBtn');
    if (updateBtn) updateBtn.disabled = true;
}

// 7. Send AJAX update with the newly selected status
async function changeStatus(newStatus) {
    if (!selectedSummaryId) return;

    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfInput) {
        alert("CSRF token not found.");
        return;
    }

    try {
        const response = await fetch(`/accounts/update-order-status/${selectedSummaryId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfInput.value,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            const row = document.getElementById(`row-${selectedSummaryId}`);
            if (row) {
                row.setAttribute('data-status', newStatus);
                
                const statusMap = {
                    'PEN': { text: 'Pending', cls: 'status-pending' },
                    'PRE': { text: 'Preparing', cls: 'status-preparing' },
                    'PAC': { text: 'Packaged', cls: 'status-packaged' },
                    'SHP': { text: 'Shipped', cls: 'status-shipped' },
                    'CAN': { text: 'Cancelled', cls: 'status-cancelled' }
                };

                const badge = row.querySelector('.status-badge');
                if (badge) {
                    badge.textContent = statusMap[newStatus].text;
                    badge.className = `status-badge ${statusMap[newStatus].cls}`; 
                }
            }
            applyAllFilters(false);
        } else {
            alert("Something went wrong updating the order.");
        }
    } catch (error) {
        console.error("Error updating status:", error);
        alert("Network error occurred.");
    }
}

// 8. Send AJAX to Cancel Subscription
async function cancelSubscription(subId) {
    if (!confirm("Are you sure you want to cancel this subscription?\n\nThis will stop future orders from generating and cancel any existing future orders (except the nearest incoming one).")) {
        return;
    }

    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfInput) return;

    try {
        const response = await fetch(`/accounts/cancel-subscription/${subId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfInput.value,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            alert("Subscription cancelled successfully.");
            // Reload the page to refresh the active subscriptions and cancelled orders table
            window.location.reload(); 
        } else {
            alert("Something went wrong cancelling the subscription.");
        }
    } catch (error) {
        console.error("Error cancelling subscription:", error);
        alert("Network error occurred.");
    }
}

// 9. Subscription table filtering + pagination
function applySubFilters(resetPage = true) {
    if (resetPage) subCurrentPage = 1;

    const checkedStatuses = Array.from(
        document.querySelectorAll('.sub-status-filter:checked')
    ).map(cb => cb.value);

    let matchingRows = [];

    document.querySelectorAll('.sub-row').forEach(row => {
        const status = row.getAttribute('data-sub-status');
        if (checkedStatuses.includes(status)) {
            matchingRows.push(row);
        } else {
            row.style.display = 'none';
        }
    });

    // Pagination
    const totalRows = matchingRows.length;
    const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

    if (subCurrentPage > totalPages) subCurrentPage = totalPages;

    const startIndex = (subCurrentPage - 1) * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;

    matchingRows.forEach((row, index) => {
        row.style.display = (index >= startIndex && index < endIndex) ? '' : 'none';
    });

    renderSubPagination(totalPages);
}

function renderSubPagination(totalPages) {
    const container = document.getElementById('subPaginationContainer');
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '<ul class="pagination mb-0 shadow-sm">';

    html += `<li class="page-item ${subCurrentPage === 1 ? 'disabled' : ''}">
                <button class="page-link" onclick="goToSubPage(${subCurrentPage - 1})" style="color: var(--brand);">Previous</button>
             </li>`;

    for (let i = 1; i <= totalPages; i++) {
        const activeClass = subCurrentPage === i ? 'active' : '';
        const activeStyle = subCurrentPage === i
            ? 'background-color: #3a4b53; border-color: #3a4b53; color: #fff;'
            : 'color: var(--brand);';
        html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="goToSubPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
    }

    html += `<li class="page-item ${subCurrentPage === totalPages ? 'disabled' : ''}">
                <button class="page-link" onclick="goToSubPage(${subCurrentPage + 1})" style="color: var(--brand);">Next</button>
             </li>`;

    html += '</ul>';
    container.innerHTML = html;
}

function goToSubPage(pageNumber) {
    subCurrentPage = pageNumber;
    applySubFilters(false);
}

function clearSubFilters() {
    document.getElementById('subFilterActive').checked = true;
    document.getElementById('subFilterPaused').checked = true;
    document.getElementById('subFilterCancelled').checked = false;
    applySubFilters(true);
}

// 10. Pause / Resume Subscription
async function toggleSubscription(subId) {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfInput) return;

    try {
        const response = await fetch(`/accounts/toggle-subscription/${subId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfInput.value,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            const row = document.getElementById(`sub-row-${subId}`);
            if (row) {
                row.setAttribute('data-sub-status', data.new_status);

                const badge = row.querySelector('.sub-status-badge');
                if (badge) {
                    badge.textContent = data.new_status_display;
                    badge.className = 'status-badge sub-status-badge';
                    if (data.new_status === 'ACTIVE') badge.classList.add('status-packaged');
                    else if (data.new_status === 'PAUSED') badge.classList.add('status-pending');
                    else badge.classList.add('status-cancelled');
                }
            }
            // Reload to refresh the details template buttons
            window.location.reload();
        } else {
            alert("Something went wrong toggling the subscription.");
        }
    } catch (error) {
        console.error("Error toggling subscription:", error);
        alert("Network error occurred.");
    }
}

// 11. Initialize when the DOM loads
document.addEventListener('DOMContentLoaded', () => {
    const resetAndFilter = () => applyAllFilters(true);

    document.getElementById('filterOrderId').addEventListener('input', resetAndFilter);
    document.getElementById('filterCustomerName').addEventListener('input', resetAndFilter);
    document.getElementById('filterDateFrom').addEventListener('change', resetAndFilter);
    document.getElementById('filterDateTo').addEventListener('change', resetAndFilter);
    
    document.querySelectorAll('.status-filter').forEach(cb => {
        cb.addEventListener('change', resetAndFilter);
    });

    // Subscription status filter listeners
    document.querySelectorAll('.sub-status-filter').forEach(cb => {
        cb.addEventListener('change', () => applySubFilters(true));
    });
    
    applyAllFilters(true);
    applySubFilters(true);

    // Auto-open order from notification
    const params = new URLSearchParams(window.location.search);
    const openOrderId = params.get("open_order");

    if (openOrderId) {
        // Delay to ensure rows are rendered + filters applied
        setTimeout(() => {
            applyAllFilters(false, false);

            const row = document.getElementById(`row-${openOrderId}`);
            if (row) {
                row.scrollIntoView({ behavior: "smooth", block: "center" });
                showOrderDetails(openOrderId, row);
            }
        }, 50);
    }    
});