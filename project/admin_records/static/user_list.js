document.addEventListener("DOMContentLoaded", () => {
    
    console.log(" user_list.js LOADED");
    const modal = new bootstrap.Modal(document.getElementById("deleteUserModal"));
    const deleteText = document.getElementById("deleteUserText");
    const deleteReason = document.getElementById("deleteReason");
    const deleteUserId = document.getElementById("deleteUserId");

    // Open modal
    document.querySelectorAll(".delete-user-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            deleteText.textContent = `Are you sure you want to deactivate "${btn.dataset.userName}"?`;
            deleteUserId.value = btn.dataset.userId;
            deleteReason.value = "";
            modal.show();
        });
    });

    // Confirm deactivation
    document.getElementById("confirmDeleteBtn").addEventListener("click", () => {
        const reason = deleteReason.value.trim();
        const id = deleteUserId.value;

        if (!reason) {
            alert("Please provide a reason.");
            return;
        }

        fetch(`/admin_records/users/${id}/deactivate/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ reason })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                modal.hide();
                location.reload();
            } else {
                alert("Error deactivating user.");
            }
        });
    });

    // Reactivate user
    document.querySelectorAll(".reactivate-user-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.userId;

            if (!confirm(`Reactivate "${btn.dataset.userName}"?`)) {
                return;
            }

            fetch(`/admin_records/users/${id}/reactivate/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                    "Content-Type": "application/json"
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert("Error reactivating user.");
                }
            });
        });
    });

});