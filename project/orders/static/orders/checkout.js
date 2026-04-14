// Main process for checkout form
document.addEventListener("DOMContentLoaded", () => {
    console.log("checkout.js loaded");
    const wrapper = document.getElementById("checkout-wrapper");
    const form = document.getElementById("checkout-form");
    const isGuest = document.getElementById("is-authenticated").value === "0";

    // ===============================
    // Disable payment options & submit when total < £1
    // ===============================
    const total = parseFloat(document.getElementById("checkout-submit")
        .textContent.match(/£([\d.]+)/)[1]);

    const checkoutDetails = document.getElementById("checkout-whole");
    const warning = document.getElementById("min-order-warning");
    const cardRadio = document.getElementById("payment-card");
    const cashRadio = document.getElementById("payment-cash");
    const submitBtn = document.getElementById("checkout-submit");

    if (total < 1) {
        warning.style.display = "block";

        // Hide all checkout details except the warning
        checkoutDetails.style.opacity = "0.4";
        checkoutDetails.style.pointerEvents = "none";

        // Disable payment options
        cardRadio.disabled = true;
        cashRadio.disabled = true;

        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.classList.add("disabled-btn");
    }

    // ===============================
    // Card payment initialisation
    // ===============================
    let stripe = null;
    let elements = null;

    if (STRIPE_CLIENT_SECRET && STRIPE_CLIENT_SECRET.startsWith("pi_")) {
        stripe = Stripe(STRIPE_PUBLISHABLE_KEY);

        elements = stripe.elements({
            clientSecret: STRIPE_CLIENT_SECRET,
            wallets: { link: "never" }
        });

        const paymentElement = elements.create("payment", {
            wallets: { link: "never" }
        });

        paymentElement.mount("#payment-element");
    } else {
        console.warn("Stripe not initialised: no valid client secret.");
    }

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

            // Clear existing options
            timeField.innerHTML = '<option value="">Select a time slot</option>';

            const selectedDate = dateInput.value;
            const minStr = deliveryRadio.checked ? deliveryMin : collectionMin;
            const [minDate, minTime] = minStr.split("T");
            const earliestTime = minTime.slice(0, 5);

            let filteredSlots = slots;

            // If user picked the earliest allowed date, filter invalid slots
            if (selectedDate === minDate) {
                filteredSlots = slots.filter(slot => {
                    const start = slot.split("-")[0];
                    return start >= earliestTime;
                });
            }

            // Add filtered slots
            filteredSlots.forEach(slot => {
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
            dateInput.value = "";          // Clear old date
            timeField.innerHTML = "";      // Clear old time slots
            updateDateConstraints();
            updateSlotOptions();
            autoSelectEarliestSlot();
        });

        collectionRadio.addEventListener("change", () => {
            dateInput.value = "";          // Clear old date
            timeField.innerHTML = "";      // Clear old time slots
            updateDateConstraints();
            updateSlotOptions();
            autoSelectEarliestSlot();
        });

        dateInput.addEventListener("change", () => {
            updateSlotOptions();
            autoSelectEarliestSlot();
        });

        // Initialise on page load
        updateDateConstraints();
        updateSlotOptions();
        autoSelectEarliestSlot();
    });

    // ===============================
    // Recurring order dropdowns
    // ===============================
    const DAY_LABELS = {MON:"Monday",TUE:"Tuesday",WED:"Wednesday",THU:"Thursday",FRI:"Friday",SAT:"Saturday",SUN:"Sunday"};
    const DATE_TO_DAY = ["SUN","MON","TUE","WED","THU","FRI","SAT"];

    document.querySelectorAll('.recurring-select').forEach(sel => {
        const producerId = sel.dataset.producerId;
        const panel = document.getElementById(`recurring-options-${producerId}`);
        if (!panel) return;

        sel.addEventListener('change', () => {
            panel.style.display = sel.value === 'yes' ? 'block' : 'none';
            if (sel.value !== 'yes') {
                // Reset child fields
                const patternSel = panel.querySelector('.recurrence-pattern');
                if (patternSel) patternSel.value = 'WEEKLY';
                const daySel = panel.querySelector('.recurrence-day-select');
                if (daySel) daySel.value = '';
                updateRecurringSummary(producerId);
            } else {
                // Auto-select recurrence day based on selected delivery date
                autoSelectRecurrenceDay(producerId);
            }
        });
    });

    // When the delivery date changes, auto-default the recurrence day
    document.querySelectorAll('.delivery-date').forEach(dateInput => {
        dateInput.addEventListener('change', () => {
            const section = dateInput.closest('.producer-delivery');
            if (!section) return;
            const producerId = section.querySelector('.producer-id')?.value;
            if (producerId) autoSelectRecurrenceDay(producerId);
        });
    });

    // When frequency or recurrence day changes, update the summary text
    document.querySelectorAll('.recurrence-pattern, .recurrence-day-select').forEach(el => {
        el.addEventListener('change', () => {
            const producerId = el.dataset.producerId || el.closest('.recurring-options')?.id?.replace('recurring-options-','');
            if (producerId) updateRecurringSummary(producerId);
        });
    });

    function autoSelectRecurrenceDay(producerId) {
        const section = document.querySelector(`.producer-delivery .producer-id[value="${producerId}"]`)?.closest('.producer-delivery');
        if (!section) return;
        const dateInput = section.querySelector('.delivery-date');
        const daySel = document.querySelector(`#recurrence-day-${producerId}`);
        if (!dateInput || !daySel || !dateInput.value) return;

        const dt = new Date(dateInput.value + 'T00:00:00');
        const dayCode = DATE_TO_DAY[dt.getDay()];
        if (dayCode) daySel.value = dayCode;
        updateRecurringSummary(producerId);
    }

    function updateRecurringSummary(producerId) {
        const summary = document.getElementById(`recurring-summary-${producerId}`);
        if (!summary) return;

        const recurringSel = document.getElementById(`is-recurring-${producerId}`);
        if (!recurringSel || recurringSel.value !== 'yes') {
            summary.textContent = '';
            return;
        }

        const pattern = document.getElementById(`recurrence-pattern-${producerId}`)?.value;
        const dayCode = document.getElementById(`recurrence-day-${producerId}`)?.value;

        if (!dayCode) {
            summary.textContent = 'Select a recurrence day to see the schedule.';
            return;
        }

        const freq = pattern === 'FORTNIGHTLY' ? 'every two weeks' : 'every week';
        const dayName = DAY_LABELS[dayCode] || dayCode;

        // Calculate the first recurring delivery date (after initial delivery)
        const section = document.querySelector(`.producer-delivery .producer-id[value="${producerId}"]`)?.closest('.producer-delivery');
        const dateInput = section?.querySelector('.delivery-date');
        let firstDeliveryText = '';

        if (dateInput?.value) {
            const initialDate = new Date(dateInput.value + 'T00:00:00');
            const targetDayIndex = Object.keys(DAY_LABELS).indexOf(dayCode);
            // JS day: 0=Sun,1=Mon,...6=Sat; our mapping: MON=0,...SUN=6
            const jsDayTarget = targetDayIndex === 6 ? 0 : targetDayIndex + 1;
            let nextDate = new Date(initialDate);
            nextDate.setDate(nextDate.getDate() + 1); // start from day after initial delivery

            // Find next occurrence of the chosen day
            while (nextDate.getDay() !== jsDayTarget) {
                nextDate.setDate(nextDate.getDate() + 1);
            }

            if (pattern === 'FORTNIGHTLY') {
                // For fortnightly, skip one more week if the gap is less than 7 days
                const gap = (nextDate - initialDate) / (1000 * 60 * 60 * 24);
                if (gap < 7) nextDate.setDate(nextDate.getDate() + 7);
            }

            const opts = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            firstDeliveryText = ` First recurring delivery: ${nextDate.toLocaleDateString('en-GB', opts)}.`;
        }

        summary.textContent = `This order will repeat ${freq} on ${dayName}.${firstDeliveryText} Recurrence begins after the initial order is delivered.`;
    }

    // ===============================
    // Handle delivery/collection addresses showing
    // ===============================

    const deliverySection = document.getElementById("delivery-address-section");
    const collectionSection = document.getElementById("collection-address-section");

    function recomputeAddressVisibility() {
        if (!deliverySection || !collectionSection) {
            return; // Guest checkout: skip this logic
        }
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
    // Billing same as delivery for guest
    // ===============================
    const sameAsDelivery = document.getElementById("billing-same-as-delivery");
    const billingFields = document.getElementById("guest-billing-fields");

    const deliveryInputs = [
        "guest_delivery_line1",
        "guest_delivery_line2",
        "guest_delivery_city",
        "guest_delivery_postcode"
    ];

    const billingInputs = [
        "guest_billing_line1",
        "guest_billing_line2",
        "guest_billing_city",
        "guest_billing_postcode"
    ];

    function syncBillingToDelivery() {
        billingInputs.forEach((billingName, index) => {
            const deliveryName = deliveryInputs[index];
            form[billingName].value = form[deliveryName].value;
        });
    }

    if (sameAsDelivery && isGuest) {
        sameAsDelivery.addEventListener("change", () => {
            if (sameAsDelivery.checked) {
                syncBillingToDelivery();
                billingFields.style.display = "none";

                // Start live syncing
                deliveryInputs.forEach(name => {
                    form[name].addEventListener("input", syncBillingToDelivery);
                });
            } else {
                billingFields.style.display = "";

                // Stop syncing
                deliveryInputs.forEach(name => {
                    form[name].removeEventListener("input", syncBillingToDelivery);
                });
            }
        });
    }

    // ===============================
    // Show card payment
    // ===============================
    const cardSection = document.getElementById("card-payment-section");
    const radios = document.querySelectorAll('input[name="payment_method"]');

    // Show or hide card section based on the default selected radio
    const selected = document.querySelector('input[name="payment_method"]:checked');
    if (selected && selected.value === "CRD") {
        cardSection.style.display = "block";
    } else {
        cardSection.style.display = "none";
    }

    // Update visibility when user changes selection
    radios.forEach(radio => {
        radio.addEventListener("change", () => {
            if (radio.value === "CRD") {
                cardSection.style.display = "block";
            } else {
                cardSection.style.display = "none";
            }
        });
    });

    // ===============================
    // Error messages
    // ===============================
    
    // Dates, time slots and main form validation
    form.addEventListener("invalid", () => {
        wrapper.classList.add("submitted");
    }, true);

    // Delivery address form validation
    const deliveryAddressForm = document.getElementById("delivery-address-create-form");
    const deliveryWrapper = document.querySelector("#new-delivery-address-form .address-wrapper");

    if (deliveryAddressForm && deliveryWrapper) {
        deliveryAddressForm.addEventListener("invalid", () => {
            deliveryWrapper.classList.add("submitted");
        }, true);
    }

    // Billing address form validation
    const billingAddressForm = document.getElementById("billing-address-create-form");
    const billingWrapper = document.querySelector("#new-billing-address-form .address-wrapper");

    if (billingAddressForm && billingWrapper) {
        billingAddressForm.addEventListener("invalid", () => {
            billingWrapper.classList.add("submitted");
        }, true);
    }

    // ===============================
    // Order form
    // ===============================
    if (!form) {
        console.warn("checkout-form not found in DOM");
        return;
    }
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        e.stopImmediatePropagation();

        try {
            console.log("Submit handler triggered");
            debugger;

            const paymentMethod = document.querySelector('input[name="payment_method"]:checked')?.value;
            console.log("paymentMethod =", paymentMethod);

            const specialInstructions = form.special_instructions.value;
            console.log("specialInstructions =", specialInstructions);

            //const deliveryAddressId = document.querySelector('select[name="delivery_address_id"]').value;
            // Use saved address for users
            let deliveryAddressId = null;
            if (!isGuest) {
                deliveryAddressId = document.querySelector('select[name="delivery_address_id"]').value;
            }
            let billingAddressId = null;
            if (!isGuest) {
                billingAddressId = document.querySelector('select[name="billing_address_id"]').value;
            }
            console.log("deliveryAddressId =", deliveryAddressId);
            console.log("billingAddressId =", billingAddressId);

            // Producer delivery/collection
            const producerBlocks = document.querySelectorAll('.producer-delivery');
            const producerData = {};
            let missingFields = false;

            producerBlocks.forEach(block => {
                const producerId = block.querySelector('.producer-id').value;

                const method = block.querySelector(`input[name="delivery_or_collection_${producerId}"]:checked`)?.value;
                const date = block.querySelector(`input[name="delivery_date_${producerId}"]`)?.value;
                const time = block.querySelector(`select[name="delivery_time_${producerId}"]`)?.value;
                
                // Recurring order fields
                const recurringSelect = block.querySelector(`select[name="is_recurring_${producerId}"]`);
                const isRecurring = recurringSelect ? recurringSelect.value === 'yes' : false;
                const recurrencePattern = block.querySelector(`select[name="recurrence_pattern_${producerId}"]`)?.value || "";
                const recurrenceDay = block.querySelector(`select[name="recurrence_day_${producerId}"]`)?.value || "";

                // Validate all required fields exist per producer
                if (!method || !date || !time) {
                    missingFields = true; 
                }

                // Validate recurrence day is selected when recurring is enabled
                if (isRecurring && !recurrenceDay) {
                    missingFields = true;
                }

                producerData[`delivery_or_collection_${producerId}`] = method;
                producerData[`delivery_date_${producerId}`] = date;
                producerData[`delivery_time_${producerId}`] = time;
                producerData[`is_recurring_${producerId}`] = isRecurring;
                producerData[`recurrence_pattern_${producerId}`] = recurrencePattern;
                producerData[`recurrence_day_${producerId}`] = recurrenceDay;
            });

            console.log("producerData =", producerData);

            // Validation for required fields
            if (!paymentMethod || missingFields) {
                wrapper.classList.add("submitted");
                alert("Please complete all required fields before placing your order.");
                return;
            }

            // Logged-in users must select an address
            if (!isGuest && !deliveryAddressId) {
                alert("Please select a delivery address.");
                return;
            }
            if (!isGuest && !billingAddressId) {
                alert("Please select a billing address.");
                return;
            }

            // Guest fields
            let guestData = {};
            if (isGuest) {
                guestData = {
                    guest_name: form.guest_name.value,
                    guest_email: form.guest_email.value,
                    guest_phone: form.guest_phone.value,

                    guest_delivery_line1: form.guest_delivery_line1.value,
                    guest_delivery_line2: form.guest_delivery_line2.value,
                    guest_delivery_city: form.guest_delivery_city.value,
                    guest_delivery_postcode: form.guest_delivery_postcode.value,

                    guest_billing_line1: form.guest_billing_line1.value,
                    guest_billing_line2: form.guest_billing_line2.value,
                    guest_billing_city: form.guest_billing_city.value,
                    guest_billing_postcode: form.guest_billing_postcode.value,
                };
            }
            console.log("guestData =", guestData);

            // ===============================
            // Branch by payment method
            // ===============================

            // Store details first
            let saveResponse;
            try {
                saveResponse = await fetch("/orders/checkout/save/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
                    },
                    body: JSON.stringify({
                        delivery_address_id: deliveryAddressId,
                        billing_address_id: billingAddressId,
                        payment_method: paymentMethod,
                        special_instructions: specialInstructions,
                        is_guest: isGuest,
                        ...guestData,
                        ...producerData
                    })
                });

                if (!saveResponse.ok) {
                    throw new Error("Save endpoint returned " + saveResponse.status);
                }
                console.log("Saved successfully.");
            } catch (err) {
                console.error("Failed to save checkout data:", err);
                alert("Could not save your checkout details. Please try again.");
                return;
            }

            console.log("Saved successfully.")

            if (paymentMethod === "CSH") {
                try {
                    // Submit normally to COD view
                    console.log("Submit handler CASH triggered");
                    form.action = "/orders/checkout/cod/";
                    form.submit();
                } catch (err) {
                    console.error("COD submission failed:", err);
                    alert("Could not submit your cash order.");
                }
                console.log("CASH branch returned");
                return;
            }

            console.log("Reached card payment.")

            // Card payment
            if (!stripe || !elements) {
                console.warn("Stripe not initialised — cannot process card payment.");
                return;
            }

            try{
                 const result = await stripe.confirmPayment({
                    elements,
                    confirmParams: {
                        return_url: RETURN_URL,
                    },
                    setup_future_usage: null
                });
                console.log("Card payment came back =", result);

                if (result.error) {
                    let userMessage = "Something went wrong. Please try again."; 
                    
                    // Stripe provided error
                    switch (result.error.type) {
                        case "card_error": 
                            // Safe to show (insufficient funds etc.)
                            userMessage = result.error.message;
                            break;
                        
                        case "validation_error":
                            // Hide specifics
                            userMessage = "Your card details are incorrect. Please check them and try again.";
                            break;
                        
                        case "api_connection_error":
                            userMessage = "We couldn't reach your bank. Please check your connection and try again.";
                            break;
                        
                        case "api_error":
                            userMessage = "A server error occurred. Please try again in a moment.";
                            break;
                        
                        case "authentication_error":
                            userMessage = "Authentication failed. Please try again.";
                            break;
                        
                        default:
                            userMessage = "Payment could not be processed. Please try again.";
                    }

                    document.querySelector("#payment-errors").textContent = userMessage;
                    errorBox.style.display = "block";
                    console.error("Stripe error:", result.error);
                }
            } catch (err) {
                console.error("Stripe confirmPayment crashed:", err);
                alert("Payment could not be completed. Please try again.");
            }
        } catch (err) {
            console.error("Checkout submit failed:", err);
            alert("Something went wrong while processing your order. Please try again.");
        }
    });
});

// ===============================
// Handle new addresses and update display
// ===============================
async function handleAddressForm(formId, selectId, previewId) {
    const addressForm = document.getElementById(formId);
    const select = document.getElementById(selectId);
    const preview = document.getElementById(previewId);

    if (!addressForm) return;

    addressForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = {
            line1: addressForm.line1.value,
            line2: addressForm.line2.value,
            city: addressForm.city.value,
            postcode: addressForm.postcode.value,
            is_default_delivery: addressForm.is_default_delivery?.checked || false,
            is_default_billing: addressForm.is_default_billing?.checked || false
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

        // Force the triggering dropdown to select the new address
        select.value = data.id;
        select.dispatchEvent(new Event("change"));

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
        addressForm.reset();
        addressForm.parentElement.style.display = "none";
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