document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("checkout-form");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Client-side validation 
        const paymentMethod = document.querySelector('input[name="payment_method"]:checked');
        if (!paymentMethod) {
            alert("Please select a payment method");
            return;
        }

        const response = await fetch("/api/checkout/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify({
                payment_method: paymentMethod.value
            })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = `/orders/success/${data.unique_reference}/`;
        } else {
            //alert("Checkout failed: " + data.error);
            if (!response.ok) {
                alert("Checkout failed h:\n" + JSON.stringify(data, null, 2));
                return;
            }
        }
    });
});