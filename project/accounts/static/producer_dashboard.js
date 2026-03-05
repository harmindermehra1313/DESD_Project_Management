let selectedSummaryId = null;

// Pagination variables
let currentPage = 1;
const rowsPerPage = 10;

// 1. Evaluates ID, Name, Dates, Checkboxes, AND Pagination
function applyAllFilters(resetPage = true) {
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

    // Safety check: if we filter and the current page no longer exists
    if (currentPage > totalPages) {
        currentPage = totalPages;
    }

    const startIndex = (currentPage - 1) * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;

    // Loop through the matched rows and only display the 10 for the current page
    matchingRows.forEach((row, index) => {
        if (index >= startIndex && index < endIndex) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    // Handle Empty State Message
    const emptyRow = document.getElementById('emptyStateRow');
    if (emptyRow) {
        emptyRow.style.display = totalRows === 0 ? '' : 'none';
    }

    // Render the page buttons
    renderPagination(totalPages);

    // --- RESET DETAILS PANEL ---
    selectedSummaryId = null;
    document.querySelectorAll('.order-row').forEach(r => r.classList.remove('selected'));
    
    const detailOrderId = document.getElementById('detailOrderId');
    const detailsContent = document.getElementById('detailsContent');
    
    if (detailOrderId) detailOrderId.textContent = 'Select an order';
    if (detailsContent) {
        detailsContent.innerHTML = '<p class="text-muted mb-0">Click on a specific order from the table above to view complete customer details, delivery address, itemised product list, and special instructions.</p>';
    }
    
    // Disable the Change Status button since the row selection was cleared
    const updateBtn = document.getElementById('updateStatusBtn');
    if (updateBtn) {
        updateBtn.disabled = true;
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
    
    // "Previous" Button
    html += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <button class="page-link" onclick="goToPage(${currentPage - 1})" style="color: var(--brand);">Previous</button>
             </li>`;

    // Numbered Pages
    for (let i = 1; i <= totalPages; i++) {
        const activeClass = currentPage === i ? 'active' : '';
        const activeStyle = currentPage === i ? 'background-color: #3a4b53; border-color: #3a4b53; color: #fff;' : 'color: var(--brand);';
        
        html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="goToPage(${i})" style="${activeStyle}">${i}</button>
                 </li>`;
    }

    // "Next" Button
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
    
    // Reset Checkboxes
    document.getElementById('filterPen').checked = true;
    document.getElementById('filterPre').checked = true;
    document.getElementById('filterPac').checked = true;
    document.getElementById('filterShp').checked = false;

    // Apply filters and reset to page 1
    applyAllFilters(true); 
}

// 5. Highlight row and show details
function showOrderDetails(summaryId, rowElement) {
    selectedSummaryId = summaryId;

    document.querySelectorAll('.order-row').forEach(row => row.classList.remove('selected'));
    rowElement.classList.add('selected');

    const orderRef = rowElement.cells[0].innerText;
    document.getElementById('detailOrderId').textContent = `Order ${orderRef}`;

    const templateContent = document.getElementById(`details-template-${summaryId}`).innerHTML;
    document.getElementById('detailsContent').innerHTML = templateContent;

    const updateBtn = document.getElementById('updateStatusBtn');
    if (updateBtn) updateBtn.disabled = false;
}

// 6. Send AJAX update with the newly selected status, then manipulate DOM
async function changeStatus(newStatus) {
    if (!selectedSummaryId) return;

    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfInput) {
        alert("CSRF token not found.");
        return;
    }
    const csrfToken = csrfInput.value;

    try {
        const response = await fetch(`/accounts/update-order-status/${selectedSummaryId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
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

// 7. Initialize when the DOM loads
document.addEventListener('DOMContentLoaded', () => {
    const resetAndFilter = () => applyAllFilters(true);

    // Attach live event listeners to our text and date inputs
    document.getElementById('filterOrderId').addEventListener('input', resetAndFilter);
    document.getElementById('filterCustomerName').addEventListener('input', resetAndFilter);
    document.getElementById('filterDateFrom').addEventListener('change', resetAndFilter);
    document.getElementById('filterDateTo').addEventListener('change', resetAndFilter);
    
    // Attach change listeners to all status checkboxes
    document.querySelectorAll('.status-filter').forEach(cb => {
        cb.addEventListener('change', resetAndFilter);
    });
    
    // Run the filter immediately on page load
    applyAllFilters(true);
});