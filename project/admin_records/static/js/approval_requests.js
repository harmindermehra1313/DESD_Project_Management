function showProductDetails(id) {
    const template = document.getElementById(`product-template-${id}`);

    if (!template) {
        console.error("Product template not found:", id);
        return;
    }

    const modalBody = document.getElementById("productDetailsContent");
    modalBody.innerHTML = template.innerHTML;

    const modal = new bootstrap.Modal(document.getElementById("productDetailsModal"));
    modal.show();
}

// ===============================
//   OPEN REJECT MODAL
// ===============================
function openRejectModal(productId) {
    console.log("DEBUG: openRejectModal() called with:", productId);

    const idField = document.getElementById('rejectProductId');
    const reasonField = document.getElementById('rejectReasonInput');

    if (!idField) {
        console.error("ERROR: rejectProductId element NOT FOUND");
        return;
    }
    if (!reasonField) {
        console.error("ERROR: rejectReasonInput element NOT FOUND");
        return;
    }

    idField.value = productId;
    reasonField.value = "";

    console.log("DEBUG: rejectProductId set to:", idField.value);

    const modal = new bootstrap.Modal(document.getElementById('rejectReasonModal'));
    modal.show();
}



// ===============================
//   SUBMIT REJECT REASON
// ===============================
async function submitRejectReason() {
    console.log("DEBUG: submitRejectReason() called");

    const idField = document.getElementById('rejectProductId');
    const reasonField = document.getElementById('rejectReasonInput');
    const errorEl = document.getElementById('rejectError');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

    console.log("DEBUG: rejectProductId element:", idField);
    console.log("DEBUG: rejectReasonInput element:", reasonField);

    if (!idField) {
        console.error("ERROR: rejectProductId is NULL");
        return;
    }
    if (!reasonField) {
        console.error("ERROR: rejectReasonInput is NULL");
        return;
    }

    const productId = idField.value;
    const reason = reasonField.value.trim();

    console.log("DEBUG: rejectProductId.value =", productId);
    console.log("DEBUG: rejectReasonInput.value =", reason);

    if (!reason) {
        errorEl.textContent = "Please enter a rejection reason.";
        errorEl.classList.remove("d-none");
        return;
    }

    try {
        const response = await fetch(`/admin_records/products/${productId}/reject/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken.value,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ reason })
        });

        const data = await response.json();
        console.log("DEBUG: server response:", data);

        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('rejectReasonModal')).hide();
            window.location.reload();
        } else {
            errorEl.textContent = data.error || "Error rejecting product.";
            errorEl.classList.remove("d-none");
        }

    } catch (err) {
        console.error("Reject error:", err);
        errorEl.textContent = "Network error. Please try again.";
        errorEl.classList.remove("d-none");
    }
}