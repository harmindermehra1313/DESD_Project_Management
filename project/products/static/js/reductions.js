// --- CSRF helper ---
function getCSRFToken() {
    return document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="))
        ?.split("=")[1];
}

async function apiPatch(url, payload) {
    const response = await fetch(url, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const text = await response.text();
        let friendly = "Something went wrong. Please try again or contact support if the issue continues.";

        try {
            const json = JSON.parse(text);

            // Field-specific errors
            if (json.surplus_discount_percentage) {
                friendly = json.surplus_discount_percentage[0];
            }
            else if (json.surplus_expiry) {
                friendly = json.surplus_expiry[0];
            }
            else if (json.surplus_note) {
                friendly = json.surplus_note[0];
            }
            else if (json.detail) {
                friendly = json.detail;
            }
        } catch {
            // Fallback for HTML/plain text errors
                friendly = "Something went wrong. Please try again or contact support if the issue continues.";
        }

        showError(friendly);
        throw new Error("API error");
    }

    return response.json();
}

function showError(message) {
    const banner = document.getElementById("errorBanner");
    if (!banner) return;

    banner.textContent = message;
    banner.classList.remove("d-none");
    banner.classList.add("show");
}

function showSuccess(message) {
    const banner = document.getElementById("successBanner");
    if (!banner) return;

    banner.textContent = message;
    banner.classList.remove("d-none");
    banner.classList.add("show");
}

function markInvalid(id) {
    const el = document.getElementById(id);
    if (!el) return;

    el.classList.add("is-invalid");

    setTimeout(() => {
        el.classList.remove("is-invalid");
    }, 3000);
}

function removeSelectOption(selectId, value) {
    const select = document.getElementById(selectId);
    if (!select) return;
    const option = select.querySelector(`option[value="${value}"]`);
    if (option) option.remove();
}

function addSelectOption(selectId, value, label, expiry) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    opt.dataset.expiry = expiry;
    select.appendChild(opt);
}

function formatDiscount(value) {
    return Number(value).toFixed(2).replace(/\.00$/, "");
}

function resetSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    select.value = ""; // selects the default option
}

function hideSection(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("d-none");
}

function showSection(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("d-none");
}

function buildReductionLabel(batch) {
    // Used for update/cancel dropdowns (active reductions)
    const typeLabel = batch.expiry_type === "UB" ? "Use by" : "Best before";

    const productExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    const dealExpiry = new Date(batch.surplus_expiry).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    return `${batch.product.name} — ${formatDiscount(batch.surplus_discount_percentage)}% off — ${batch.remaining_quantity} in stock — ${typeLabel}: ${productExpiry} (deal ends: ${dealExpiry})`;
}

function buildAvailableLabel(batch) {
    if (!batch || !batch.product || !batch.product.name) {
        console.error("Unexpected batch shape in buildAvailableLabel:", batch);
        return "Unknown product";
    }
    // Used for "Add Reduction" dropdown (no deal yet)
    const typeLabel = batch.expiry_type === "UB" ? "Use by" : "Best before";

    const productExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    return `${batch.product.name} — ${batch.remaining_quantity} in stock — ${typeLabel}: ${productExpiry}`;
}

function clearMessages() {
    const error = document.getElementById("errorBanner");
    const success = document.getElementById("successBanner");

    if (error) {
        error.classList.add("d-none");
        error.classList.remove("show");
    }

    if (success) {
        success.classList.add("d-none");
        success.classList.remove("show");
    }
}

function addToCurrentReductions(batch) {
    const list = document.getElementById("current-reductions-list");
    const emptyMsg = list.querySelector(".no-current-reductions");

    // Remove empty message if present
    if (emptyMsg) emptyMsg.remove();

    const li = document.createElement("li");
    li.className = "list-group-item d-flex justify-content-between align-items-center";

    const type = batch.expiry_type === "UB" ? "Use by" : "Best before";
    const productExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    const dealExpiry = new Date(batch.surplus_expiry).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    li.textContent =
        `${batch.product.name} — ${formatDiscount(batch.surplus_discount_percentage)}% off — ` +
        `${batch.remaining_quantity} in stock — ${type}: ${productExpiry} (deal ends: ${dealExpiry})`;

    const badge = document.createElement("span");
    badge.className = "badge bg-success";
    badge.textContent = "Active";

    li.appendChild(badge);
    list.appendChild(li);
}

function updateCurrentReduction(batch) {
    const list = document.getElementById("current-reductions-list");
    const items = list.querySelectorAll("li");

    items.forEach(li => {
        if (li.textContent.includes(batch.product.name)) {
            const type = batch.expiry_type === "UB" ? "Use by" : "Best before";
            const productExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
            });

            const dealExpiry = new Date(batch.surplus_expiry).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "long",
                year: "numeric",
            });

            // Replace the text content but keep the badge
            li.childNodes[0].textContent =
                `${batch.product.name} — ${formatDiscount(batch.surplus_discount_percentage)}% off — ` +
                `${batch.remaining_quantity} in stock — ${type}: ${productExpiry} (deal ends: ${dealExpiry})`;
        }
    });
}

function moveToPastReductions(batch) {
    const currentList = document.getElementById("current-reductions-list");
    const pastList = document.getElementById("past-reductions-list");

    // Remove from current
    const currentItems = currentList.querySelectorAll("li");
    currentItems.forEach(li => {
        if (li.textContent.includes(batch.product.name)) {
            li.remove();
        }
    });

    // If current list is now empty, add empty message
    if (currentList.children.length === 0) {
        const emptyLi = document.createElement("li");
        emptyLi.className = "list-group-item text-muted no-current-reductions";
        emptyLi.textContent = "You currently have no active reductions.";
        currentList.appendChild(emptyLi);
    }

    // Build past reduction entry
    const li = document.createElement("li");
    li.className = "list-group-item d-flex justify-content-between align-items-center";

    const type = batch.expiry_type === "UB" ? "Use by" : "Best before";
    const productExpiry = new Date(batch.expiry_date).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    // Use snapshot fields returned by the API
    const discount = batch.snapshot_discount;
    const dealEnded = batch.snapshot_expiry || batch.ended_at;
    const endedReason = batch.ended_reason;

    const dealEndedFormatted = dealEnded
        ? new Date(dealEnded).toLocaleDateString("en-GB", {
              day: "numeric",
              month: "long",
              year: "numeric",
          })
        : null;

    // Build text
    let text = `${batch.product.name} — `;

    if (discount) {
        text += `${formatDiscount(discount)}% off — `;
    } else {
        text += `Cancelled reduction — `;
    }

    text += `${type}: ${productExpiry}`;

    if (endedReason === "expired" && dealEndedFormatted) {
        text += ` (deal ended: ${dealEndedFormatted})`;
    } else if (endedReason === "cancelled" && dealEndedFormatted) {
        text += ` (cancelled: ${dealEndedFormatted})`;
    }

    li.textContent = text;

    const badge = document.createElement("span");
    badge.className = "badge bg-secondary";
    badge.textContent = "Ended";

    li.appendChild(badge);

    // Remove empty message in past list if present
    const emptyPast = pastList.querySelector(".no-past-reductions");
    if (emptyPast) emptyPast.remove();

    pastList.appendChild(li);
}

/* ============================================================
   DATE VALIDATION HELPERS
============================================================ */

// Set min date to NOW for all datetime-local inputs
function setMinDate(input) {
    const today = new Date().toISOString().split("T")[0];
    input.min = today;
}

// Set max date based on product expiry
function setMaxDate(input, expiryDate) {
    if (!expiryDate) return;
    input.max = expiryDate;
}

// When selecting a product, update the expiry limit
function handleProductSelection(selectId, expiryInputId) {
    const select = document.getElementById(selectId);
    const expiryInput = document.getElementById(expiryInputId);

    if (!select || !expiryInput) return;

    select.addEventListener("change", () => {
        const option = select.options[select.selectedIndex];
        const expiry = option.dataset.expiry;

        setMinDate(expiryInput);
        setMaxDate(expiryInput, expiry);
    });
}

// Initialize date limits on page load and listeners on dropdowns
document.addEventListener("DOMContentLoaded", () => {
    handleProductSelection("add_product_id", "add_expiry");
    handleProductSelection("update_reduction_id", "update_expiry");

    // Always set min date for update expiry
    const updateExpiry = document.getElementById("update_expiry");
    if (updateExpiry) setMinDate(updateExpiry);

    const addExpiry = document.getElementById("add_expiry");
    if (addExpiry) setMinDate(addExpiry);

    // Update select and cancel dropdowns
    const updateSelect = document.getElementById("update_reduction_id");
    const cancelSelect = document.getElementById("cancel_reduction_id");

    if (updateSelect) {
        updateSelect.addEventListener("change", () => {
            if (updateSelect.value === "") hideSection("updateFormSection");
            else showSection("updateFormSection");
        });
    }

    if (cancelSelect) {
        cancelSelect.addEventListener("change", () => {
            if (cancelSelect.value === "") hideSection("cancelFormSection");
            else showSection("cancelFormSection");
        });
    }

    // Clear messages if tab changes
    document.querySelectorAll('button[data-bs-toggle="tab"], a[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', () => {
            clearMessages();
        });
    });
});

/* ============================================================
   CREATE
============================================================ */

async function createReduction() {
    clearMessages();
    const id = document.getElementById("add_product_id").value;
    const discount = document.getElementById("add_discount").value;
    const expiry = document.getElementById("add_expiry").value;
    const note = document.getElementById("add_note").value;

    if (!id) {
        markInvalid("add_product_id");
        return showError("Please select a product batch.");
    }

    if (discount === "" || Number(discount) < 1 || Number(discount) > 90) {
        markInvalid("add_discount");
        return showError("Please enter a discount between 1% and 90%.");
    }


    if (!expiry) {
        markInvalid("add_expiry");
        return showError("Please choose a valid expiry date.");
    }

    const updated = await apiPatch(`/products/api/surplus/${id}/create/`, {
        surplus_discount_percentage: discount,
        surplus_expiry: expiry,
        surplus_note: note
    });

    // UI updates
    removeSelectOption("add_product_id", id);

    // Add to update + cancel dropdowns
    const label = buildReductionLabel(updated);

    addSelectOption("update_reduction_id", updated.id, label, updated.expiry_date);
    addSelectOption("cancel_reduction_id", updated.id, label, updated.expiry_date);
    
    // Re-enable update/cancel dropdowns if they were disabled
    const updateSelectEl = document.getElementById("update_reduction_id");
    const cancelSelectEl = document.getElementById("cancel_reduction_id");

    if (updateSelectEl) updateSelectEl.disabled = false;
    if (cancelSelectEl) cancelSelectEl.disabled = false;

    const updateButtonEl = document.querySelector("#updateFormSection button.reduction-btn");
    const cancelButtonEl = document.querySelector("#cancelFormSection button.reduction-btn");

    if (updateButtonEl) updateButtonEl.disabled = false;
    if (cancelButtonEl) cancelButtonEl.disabled = false;

    // Reset add form
    resetSelect("add_product_id");
    document.getElementById("add_discount").value = "";
    document.getElementById("add_expiry").value = "";
    document.getElementById("add_note").value = "";

    addToCurrentReductions(updated);

    showSuccess("Surplus reduction created successfully!");
}

/* ============================================================
   UPDATE
============================================================ */

async function updateReduction() {
    clearMessages();
    const id = document.getElementById("update_reduction_id").value;
    const discount = document.getElementById("update_discount").value;
    const expiry = document.getElementById("update_expiry").value;
    const note = document.getElementById("update_note").value;

    if (!id) {
        markInvalid("update_reduction_id");
        return showError("No reductions available to update.");
    }

    const updated = await apiPatch(`/products/api/surplus/${id}/update/`, {
        ...(discount && { surplus_discount_percentage: discount }),
        ...(expiry && { surplus_expiry: expiry }),
        ...(note && { surplus_note: note })
    });

    // Update dropdown labels after successful update
    const newLabel = buildReductionLabel(updated);

    // Update the UPDATE dropdown option
    const updateOption = document.querySelector(
        `#update_reduction_id option[value="${id}"]`
    );
    if (updateOption) {
        updateOption.textContent = newLabel;
        updateOption.dataset.expiry = updated.expiry_date;
    }

    // Update the CANCEL dropdown option
    const cancelOption = document.querySelector(
        `#cancel_reduction_id option[value="${id}"]`
    );
    if (cancelOption) {
        cancelOption.textContent = newLabel;
        cancelOption.dataset.expiry = updated.expiry_date;
    }

    // Reset dropdown + hide form
    resetSelect("update_reduction_id");
    hideSection("updateFormSection");

    // Reset form
    document.getElementById("update_discount").value = "";
    document.getElementById("update_expiry").value = "";
    document.getElementById("update_note").value = "";

    updateCurrentReduction(updated);

    showSuccess("Reduction updated successfully!");
}

/* ============================================================
   CANCEL
============================================================ */
async function cancelReduction() {
    clearMessages();
    const id = document.getElementById("cancel_reduction_id").value;

    if (!id) {
        markInvalid("cancel_reduction_id");
        return showError("No reductions available to cancel.");
    }

    const updated = await apiPatch(`/products/api/surplus/${id}/cancel/`, {});

    // Add back to available products
    //const label = `${updated.product.name} — ${updated.remaining_quantity} in stock — ${updated.expiry_type === "UB" ? "UB" : "BB"}: ${updated.expiry_date}`;
    const addLabel = buildAvailableLabel(updated);
    addSelectOption("add_product_id", updated.id, addLabel, updated.expiry_date);


    // Remove from update & cancel dropdowns
    removeSelectOption("update_reduction_id", id);
    removeSelectOption("cancel_reduction_id", id);

    // Reset dropdowns to default
    resetSelect("update_reduction_id");
    resetSelect("cancel_reduction_id");

    // Hide forms
    hideSection("updateFormSection");
    hideSection("cancelFormSection");

    moveToPastReductions(updated);

    showSuccess("Reduction cancelled successfully!");
    handleNoReductionsState();
}

function handleNoReductionsState() {
    const updateSelect = document.getElementById("update_reduction_id");
    const cancelSelect = document.getElementById("cancel_reduction_id");
    const updateButton = document.querySelector("#updateFormSection button.reduction-btn");
    const cancelButton = document.querySelector("#cancelFormSection button.reduction-btn");

    // If the selects exist and only have the default option left
    if (updateSelect && updateSelect.options.length === 1) {
        updateSelect.disabled = true;
        if (updateButton) updateButton.disabled = true;
    }

    if (cancelSelect && cancelSelect.options.length === 1) {
        cancelSelect.disabled = true;
        if (cancelButton) cancelButton.disabled = true;
    }
}