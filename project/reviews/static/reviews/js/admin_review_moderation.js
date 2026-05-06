document.addEventListener("DOMContentLoaded", () => {
    const forms = document.querySelectorAll(".js-moderation-form");
    const confirmModalElement = document.getElementById("moderationConfirmModal");
    const confirmMessageElement = document.getElementById("moderationConfirmMessage");
    const confirmSubmitButton = document.getElementById("moderationConfirmSubmit");

    let pendingForm = null;
    let pendingButton = null;

    const confirmModal =
        confirmModalElement && window.bootstrap && bootstrap.Modal
            ? new bootstrap.Modal(confirmModalElement)
            : null;

    function setInvalid(textarea, message) {
        textarea.classList.add("is-invalid");

        const feedback = textarea
            .closest(".moderation-field")
            ?.querySelector(".invalid-feedback");

        if (feedback) {
            feedback.textContent = message;
        }

        textarea.focus();
    }

    function clearInvalid(textarea) {
        textarea.classList.remove("is-invalid");
    }

    function updateCounter(textarea) {
        const targetId = textarea.dataset.counterTarget;

        if (!targetId) {
            return;
        }

        const counter = document.getElementById(targetId);

        if (counter) {
            counter.textContent = textarea.value.length;
        }
    }

    function showToastMessages() {
        document.querySelectorAll(".moderation-toast").forEach((toastElement) => {
            if (window.bootstrap && bootstrap.Toast) {
                const toast = new bootstrap.Toast(toastElement);
                toast.show();
            } else {
                toastElement.classList.add("show");

                setTimeout(() => {
                    toastElement.classList.remove("show");
                }, 3500);
            }
        });
    }

    function updateConfirmButtonStyle(button) {
        if (!confirmSubmitButton || !button) {
            return;
        }

        confirmSubmitButton.className = "btn";

        if (button.classList.contains("btn-danger")) {
            confirmSubmitButton.classList.add("btn-danger");
        } else if (button.classList.contains("btn-success")) {
            confirmSubmitButton.classList.add("btn-success");
        } else if (button.classList.contains("btn-warning")) {
            confirmSubmitButton.classList.add("btn-warning");
        } else {
            confirmSubmitButton.classList.add("btn-primary");
        }

        confirmSubmitButton.textContent = button.textContent.trim() || "Confirm";
    }

    function openConfirmModal(form, button, message) {
        pendingForm = form;
        pendingButton = button;

        if (confirmMessageElement) {
            confirmMessageElement.textContent = message;
        }

        updateConfirmButtonStyle(button);

        if (confirmModal) {
            confirmModal.show();
            return;
        }

        // Fallback only if Bootstrap JS is unavailable.
        const confirmed = window.confirm(message);

        if (confirmed) {
            form.dataset.confirmed = "true";
            form.requestSubmit(button);
        }
    }

    showToastMessages();

    document.querySelectorAll("[data-moderation-note]").forEach((textarea) => {
        updateCounter(textarea);

        textarea.addEventListener("input", () => {
            updateCounter(textarea);
            clearInvalid(textarea);
        });
    });

    forms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const button = event.submitter;

            if (!button) {
                return;
            }

            if (form.dataset.confirmed === "true") {
                delete form.dataset.confirmed;
                return;
            }

            const textarea = form.querySelector("[data-moderation-note]");
            const note = textarea ? textarea.value.trim() : "";
            const maxLength = textarea
                ? Number(textarea.getAttribute("maxlength") || 500)
                : 500;

            const requiresNote = button.dataset.requiresNote === "true";
            const confirmMessage =
                button.dataset.confirmMessage || "Confirm this moderation action?";

            if (textarea) {
                clearInvalid(textarea);
            }

            if (textarea && note.length > maxLength) {
                event.preventDefault();

                setInvalid(
                    textarea,
                    `Admin note must be ${maxLength} characters or fewer.`,
                );

                return;
            }

            if (textarea && requiresNote && !note) {
                event.preventDefault();

                setInvalid(
                    textarea,
                    "Admin note is required for this moderation action.",
                );

                return;
            }

            event.preventDefault();
            openConfirmModal(form, button, confirmMessage);
        });
    });

    if (confirmSubmitButton) {
        confirmSubmitButton.addEventListener("click", () => {
            if (!pendingForm || !pendingButton) {
                return;
            }

            pendingForm.dataset.confirmed = "true";

            if (confirmModal) {
                confirmModal.hide();
            }

            pendingForm.requestSubmit(pendingButton);

            pendingForm = null;
            pendingButton = null;
        });
    }

    if (confirmModalElement) {
        confirmModalElement.addEventListener("hidden.bs.modal", () => {
            pendingForm = null;
            pendingButton = null;
        });
    }
});