document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("payoutForm");
    const methodSelect = document.getElementById("payout_method");

    const bankFields = document.getElementById("bankFields");
    const paypalFields = document.getElementById("paypalFields");
    //const chequeFields = document.getElementById("chequeFields");

    const result = document.getElementById("result");

    // -----------------------------
    // Show/hide fields based on method
    // -----------------------------
    function updateFieldVisibility() {
        const method = methodSelect.value;

        bankFields.style.display = method === "BT" ? "block" : "none";
        paypalFields.style.display = method === "PP" ? "block" : "none";
        //chequeFields.style.display = method === "CHQ" ? "block" : "none";
    }

    updateFieldVisibility();
    methodSelect.addEventListener("change", updateFieldVisibility);

    // -----------------------------
    // Helper: show error
    // -----------------------------
    function setError(input, message) {
        input.classList.add("is-invalid");
        const feedback = input.parentElement.querySelector(".invalid-feedback");
        if (feedback) feedback.textContent = message;
    }

    function clearError(input) {
        input.classList.remove("is-invalid");
        const feedback = input.parentElement.querySelector(".invalid-feedback");
        if (feedback) feedback.textContent = "";
    }

    // -----------------------------
    // Auto-format sort code
    // -----------------------------
    const sortCodeInput = document.getElementById("bank_sort_code");

    sortCodeInput.addEventListener("input", function () {
        let digits = this.value.replace(/\D/g, "");
        digits = digits.substring(0, 6);

        if (digits.length >= 4) {
            this.value = digits.replace(/(\d{2})(\d{2})(\d{0,2})/, "$1-$2-$3");
        } else if (digits.length >= 2) {
            this.value = digits.replace(/(\d{2})(\d{0,2})/, "$1-$2");
        } else {
            this.value = digits;
        }
    });

    // -----------------------------
    // Numeric-only account number
    // -----------------------------
    const accountNumInput = document.getElementById("bank_account_number");

    accountNumInput.addEventListener("input", function () {
        this.value = this.value.replace(/\D/g, "").substring(0, 8);
    });

    // -----------------------------
    // Prevent "None" in bank account name
    // -----------------------------
    const bankNameInput = document.getElementById("bank_account_name");

    bankNameInput.addEventListener("input", function () {
        if (this.value.toLowerCase() === "none") {
            this.value = "";
        }
    });

    // -----------------------------
    // Validation rules
    // -----------------------------
    function validateForm() {
        let valid = true;
        const method = methodSelect.value;

        // Clear all errors first
        document.querySelectorAll(".form-control").forEach(el => clearError(el));

        // BANK TRANSFER
        if (method === "BT") {
            const name = document.getElementById("bank_account_name");
            const sortCode = document.getElementById("bank_sort_code");
            const accountNum = document.getElementById("bank_account_number");

            if (!name.value.trim()) {
                setError(name, "Bank account name is required.");
                valid = false;
            }

            const cleanedSort = sortCode.value.replace(/-/g, "");
            if (!/^\d{6}$/.test(cleanedSort)) {
                setError(sortCode, "Sort code must be 6 digits.");
                valid = false;
            }

            if (!/^\d{8}$/.test(accountNum.value)) {
                setError(accountNum, "Account number must be 8 digits.");
                valid = false;
            }
        }

        // PAYPAL
        if (method === "PP") {
            const email = document.getElementById("paypal_email");
            const emailRegex = /^[^@]+@[^@]+\.[^@]+$/;

            if (!email.value.trim()) {
                setError(email, "PayPal email is required.");
                valid = false;
            } else if (!emailRegex.test(email.value)) {
                setError(email, "Enter a valid email address.");
                valid = false;
            }
        }

        // CHEQUE
        // if (method === "CHQ") {
        //     const payee = document.getElementById("cheque_payee_name");
        //     const line1 = document.getElementById("cheque_address_line1");
        //     const city = document.getElementById("cheque_city");
        //     const postcode = document.getElementById("cheque_postcode");

        //     if (!payee.value.trim()) {
        //         setError(payee, "Cheque payee name is required.");
        //         valid = false;
        //     }

        //     if (!line1.value.trim()) {
        //         setError(line1, "Address line 1 is required.");
        //         valid = false;
        //     }

        //     if (!city.value.trim()) {
        //         setError(city, "City is required.");
        //         valid = false;
        //     }

        //     const postcodeRegex = /^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i;
        //     if (!postcodeRegex.test(postcode.value.trim())) {
        //         setError(postcode, "Enter a valid UK postcode.");
        //         valid = false;
        //     }
        // }

        return valid;
    }

    // -----------------------------
    // Submit handler
    // -----------------------------
    form.addEventListener("submit", async function (e) {
        e.preventDefault();

        // Clear previous alert
        result.innerHTML = "";

        if (!validateForm()) {
            return;
        }

        const formData = new FormData(form);
        formData.set("payout_method", methodSelect.value);

        const response = await fetch(form.dataset.apiUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": formData.get("csrfmiddlewaretoken"),
            },
            body: formData
        });

        const data = await response.json();

        // -----------------------------
        // API ERROR HANDLING
        // -----------------------------
        if (!data.success) {

            // Clear previous invalid states
            document.querySelectorAll(".form-control").forEach(el => {
                el.classList.remove("is-invalid");
                const feedback = el.parentElement.querySelector(".invalid-feedback");
                if (feedback) feedback.textContent = "";
            });

            // Build alert box
            let html = `<div class="alert alert-danger"><strong>Please fix the following:</strong><ul>`;

            for (const field in data.errors) {
                data.errors[field].forEach(msg => {
                    html += `<li>${msg}</li>`;
                });

                // Highlight fields
                const input = document.getElementById(field);
                if (input) {
                    input.classList.add("is-invalid");
                    const feedback = input.parentElement.querySelector(".invalid-feedback");
                    if (feedback) feedback.textContent = data.errors[field][0];
                }
            }

            html += `</ul></div>`;
            result.innerHTML = html;

            return;
        }

        // -----------------------------
        // SUCCESS
        // -----------------------------
        result.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
    });

});
