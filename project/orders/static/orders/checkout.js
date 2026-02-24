document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("checkout-form");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const paymentMethod = document.querySelector('input[name="payment_method"]:checked')?.value;
        const deliveryMethod = document.querySelector('input[name="delivery_or_collection"]:checked')?.value;
        const deliveryDate = form.delivery_date.value;
        const specialInstructions = form.special_instructions.value;

        if (!paymentMethod || !deliveryMethod || !deliveryDate) {
            alert("Please complete all required fields before placing your order.");
            return;
        }

        const response = await fetch("/api/checkout/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify({
                payment_method: paymentMethod,
                delivery_or_collection: deliveryMethod,
                delivery_date: deliveryDate,
                special_instructions: specialInstructions
            })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = `/orders/success/${data.unique_reference}/`;
        } else {
            alert("Checkout failed:\n" + JSON.stringify(data, null, 2));
        }
    });
});