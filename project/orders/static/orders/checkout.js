// Main process for checkout form
document.addEventListener("DOMContentLoaded", () => {
    // ===============================
    // Address selector toggles
    // ===============================

    function setupAddressToggle(selectId, formWrapperId) {
        const select = document.getElementById(selectId);
        const formWrapper = document.getElementById(formWrapperId);

        if (!select || !formWrapper) return;

        select.addEventListener("change", () => {
            if (select.value === "new") {
                formWrapper.style.display = "block";
            } else {
                formWrapper.style.display = "none";
            }
        });
    }

    setupAddressToggle("delivery-address-select", "new-delivery-address-form");
    setupAddressToggle("billing-address-select", "new-billing-address-form");

    // Change address preview to match menu
    function setupAddressPreview(selectId, previewId) {
        const select = document.getElementById(selectId);
        const preview = document.getElementById(previewId);

        if (!select || !preview) return;

        select.addEventListener("change", () => {
            if (select.value === "new") {
                // Do not update preview when adding a new address
                return;
            }

            const option = select.options[select.selectedIndex];

            const line1 = option.dataset.line1;
            const line2 = option.dataset.line2;
            const city = option.dataset.city;
            const postcode = option.dataset.postcode;

            preview.innerHTML = `
                <p> 
                    ${line1}<br>
                    ${line2 ? line2 + "<br>" : ""}
                    ${city}<br>
                    ${postcode}
                </p>
            `;
            
        });
    }

    setupAddressPreview("delivery-address-select", "selected-delivery-address");
    setupAddressPreview("billing-address-select", "selected-billing-address");

    // ===============================
    // Delivery and Collection date logic (multi‑producer)
    // ===============================

    // Values injected by Django
    const deliveryMin = document.getElementById("delivery-min").value;
    const collectionMin = document.getElementById("collection-min").value;
    const deliveryHintText = document.getElementById("delivery-hint").value;
    const collectionHintText = document.getElementById("collection-hint").value;

    // Slot definitions
    const deliverySlots = [
        "10:00-12:00",
        "12:00-14:00",
        "14:00-16:00",
        "16:00-18:00",
    ];

    const collectionSlots = [
        "09:00-11:00",
        "11:00-13:00",
        "13:00-15:00",
        "15:00-17:00",
    ];

    // Loop over each producer delivery section
    document.querySelectorAll('.producer-delivery').forEach(section => {

        const deliveryRadio = section.querySelector('input[value="DEL"]');
        const collectionRadio = section.querySelector('input[value="COL"]');
        const dateInput = section.querySelector('.delivery-date');
        const timeField = section.querySelector('.delivery-time');
        const dateHint = section.querySelector('.date-hint');

        if (!deliveryRadio || !collectionRadio || !dateInput || !timeField) { 
            console.warn("Missing elements in section", section); 
            return; 
        }

        function updateDateConstraints() {
            if (deliveryRadio.checked) {
                dateInput.min = deliveryMin.split("T")[0];
                if (dateHint) dateHint.textContent = deliveryHintText;
            } else {
                dateInput.min = collectionMin.split("T")[0];
                if (dateHint) dateHint.textContent = collectionHintText;
            }
        }

        function updateSlotOptions() {
            const slots = deliveryRadio.checked ? deliverySlots : collectionSlots;

            timeField.innerHTML = '<option value="">Select a time slot</option>';

            slots.forEach(slot => {
                const opt = document.createElement("option");
                opt.value = slot;
                opt.textContent = slot;
                timeField.appendChild(opt);
            });
        }

        function autoSelectEarliestSlot() {
            const selectedDate = dateInput.value;
            if (!selectedDate) {
                timeField.value = "";
                return;
            }

            const minStr = deliveryRadio.checked ? deliveryMin : collectionMin;
            const [minDate, minTime] = minStr.split("T");
            const earliestTime = minTime.slice(0, 5);

            const slots = deliveryRadio.checked ? deliverySlots : collectionSlots;

            if (selectedDate > minDate) {
                timeField.value = slots[0];
                return;
            }

            if (selectedDate === minDate) {
                const validSlot = slots.find(slot => {
                    const start = slot.split("-")[0];
                    return start >= earliestTime;
                });

                timeField.value = validSlot || "";
                return;
            }

            timeField.value = "";
        }

        // Bind events for this producer
        deliveryRadio.addEventListener("change", () => {
            updateDateConstraints();
            updateSlotOptions();
            autoSelectEarliestSlot();
        });

        collectionRadio.addEventListener("change", () => {
            updateDateConstraints();
            updateSlotOptions();
            autoSelectEarliestSlot();
        });

        dateInput.addEventListener("change", autoSelectEarliestSlot);

        // Initialise on page load
        updateDateConstraints();
        updateSlotOptions();
        autoSelectEarliestSlot();
    });

    // ===============================
    // Handle delivery/collection addresses showing
    // ===============================

    const deliverySection = document.getElementById("delivery-address-section");
    const collectionSection = document.getElementById("collection-address-section");

    function recomputeAddressVisibility() {
        const checkedRadios = document.querySelectorAll(
            '.producer-delivery input[type="radio"]:checked'
        );

        let anyDelivery = false;
        let anyCollection = false;

        const collectionProducerIds = [];

        checkedRadios.forEach(radio => {
            const section = radio.closest('.producer-delivery');
            const producerId = section.querySelector('.producer-id').value;

            if (radio.value === "DEL") {
                anyDelivery = true;
            } else if (radio.value === "COL") {
                anyCollection = true;
                collectionProducerIds.push(producerId);
            }
        });

        // Show/hide sections
        deliverySection.style.display = anyDelivery ? "" : "none";
        collectionSection.style.display = anyCollection ? "" : "none";

        // Filter collection addresses
        document.querySelectorAll('.collection-address-item').forEach(item => {
            const pid = item.dataset.producerId;
            item.style.display = collectionProducerIds.includes(pid) ? "" : "none";
        });
    }

    // Bind to all producer delivery/collection radios
    document.querySelectorAll(
        '.producer-delivery input[name^="delivery_or_collection_"]'
    ).forEach(radio => {
        radio.addEventListener("change", recomputeAddressVisibility);
    });

    // Initial state on page load
    recomputeAddressVisibility();

    // ===============================
    // Order form
    // ===============================
    const form = document.getElementById("checkout-form");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const paymentMethod = document.querySelector('input[name="payment_method"]:checked')?.value;
        const specialInstructions = form.special_instructions.value;
        const deliveryAddressId = document.querySelector('select[name="delivery_address_id"]').value;

        const producerBlocks = document.querySelectorAll('.producer-delivery');
        const producerData = {};
        let missingFields = false;

        producerBlocks.forEach(block => {
            const producerId = block.querySelector('.producer-id').value;

            const method = block.querySelector(`input[name="delivery_or_collection_${producerId}"]:checked`)?.value;
            const date = block.querySelector(`input[name="delivery_date_${producerId}"]`)?.value;
            const time = block.querySelector(`select[name="delivery_time_${producerId}"]`)?.value;
            
            // Validate all required fields exist per producer
            if (!method || !date || !time) {
                missingFields = true; 
            }

            producerData[`delivery_or_collection_${producerId}`] = method;
            producerData[`delivery_date_${producerId}`] = date;
            producerData[`delivery_time_${producerId}`] = time;
        });

        if (!paymentMethod || !deliveryAddressId || missingFields) {
            alert("Please complete all required fields before placing your order.");
            return;
        }

        const response = await fetch("/orders/checkout/api/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify({
                delivery_address_id: deliveryAddressId,
                payment_method: paymentMethod,
                special_instructions: specialInstructions,
                ...producerData
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

// ===============================
// Handle new addresses and update display
// ===============================
async function handleAddressForm(formId, selectId, previewId) {
    const form = document.getElementById(formId);
    const select = document.getElementById(selectId);
    const preview = document.getElementById(previewId);

    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = {
            line1: form.line1.value,
            line2: form.line2.value,
            city: form.city.value,
            postcode: form.postcode.value,
            is_default_delivery: form.is_default_delivery?.checked || false,
            is_default_billing: form.is_default_billing?.checked || false
        };

        const response = await fetch("/api/addresses/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            alert("Could not save address:\n" + JSON.stringify(data, null, 2));
            return;
        }

        // Add new option to dropdown
        const option = new Option(
            `${data.line1}${data.line2 ? ", " + data.line2 : ""}, ${data.city} (${data.postcode})`,
            data.id,
            true,
            true
        );
        option.dataset.line1 = data.line1;
        option.dataset.line2 = data.line2 || "";
        option.dataset.city = data.city;
        option.dataset.postcode = data.postcode;
        
        // Add new option to both dropdowns
        function insertAddressOption(select, option, shouldSelect) {
            const addNewOption = select.querySelector('option[value="new"]');
            clone = option.cloneNode(true);

            // Only select in dropdown where form was submitted
            clone.selected = shouldSelect;
            select.insertBefore(clone, addNewOption);
        }

        // Insert into both dropdowns
        const deliverySelect = document.getElementById("delivery-address-select");
        const billingSelect = document.getElementById("billing-address-select"); 
        
        // Select only in the dropdown that triggered the form
        insertAddressOption(deliverySelect, option, selectId === "delivery-address-select");
        insertAddressOption(billingSelect, option, selectId === "billing-address-select");

        // Update preview
        preview.innerHTML = `
            <p>
                ${data.line1}<br>
                ${data.line2 ? data.line2 + "<br>" : ""}
                ${data.city}<br>
                ${data.postcode}
            </p>
        `;

        // Hide form
        form.reset();
        form.parentElement.style.display = "none";
    });
}

handleAddressForm(
    "delivery-address-create-form",
    "delivery-address-select",
    "selected-delivery-address"
);

handleAddressForm(
    "billing-address-create-form",
    "billing-address-select",
    "selected-billing-address"
);