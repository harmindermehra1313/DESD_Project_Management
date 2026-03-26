// document.addEventListener("DOMContentLoaded", () => {
//     const form = document.getElementById("filtersForm");
//     if (!form) return;

//     const startInput = form.querySelector('input[name="start_date"]');
//     const endInput = form.querySelector('input[name="end_date"]');
//     const clearBtn = document.getElementById("clearFilters");
//     const rangeButtons = document.querySelectorAll(".quick-range");

//     function formatDate(d) {
//         const year = d.getFullYear();
//         const month = String(d.getMonth() + 1).padStart(2, "0");
//         const day = String(d.getDate()).padStart(2, "0");
//         return `${year}-${month}-${day}`;
//     }

//     rangeButtons.forEach(btn => {
//         btn.addEventListener("click", () => {
//             const days = parseInt(btn.dataset.range, 10);
//             const today = new Date();
//             const start = new Date();
//             start.setDate(today.getDate() - days);

//             startInput.value = formatDate(start);
//             endInput.value = formatDate(today);
//             form.submit();
//         });
//     });

//     clearBtn.addEventListener("click", () => {
//         startInput.value = "";
//         endInput.value = "";
//         form.querySelector('select[name="producer"]').value = "";
//         form.querySelector('select[name="status"]').value = "";
//         form.submit();
//     });
// });


// document.addEventListener("DOMContentLoaded", () => {
//     const form = document.getElementById("filtersForm");
//     if (!form) return;

//     const startInput = form.querySelector('input[name="start_date"]');
//     const endInput = form.querySelector('input[name="end_date"]');
//     const clearBtn = document.getElementById("clearFilters");
//     const rangeButtons = document.querySelectorAll(".quick-range");

//     function formatDate(d) {
//         const year = d.getFullYear();
//         const month = String(d.getMonth() + 1).padStart(2, "0");
//         const day = String(d.getDate()).padStart(2, "0");
//         return `${year}-${month}-${day}`;
//     }

//     // Auto-submit on any change
//     form.querySelectorAll("input, select").forEach(field => {
//         field.addEventListener("change", () => form.submit());
//     });

//     // Quick ranges
//     rangeButtons.forEach(btn => {
//         btn.addEventListener("click", () => {
//             const days = parseInt(btn.dataset.range, 10);
//             const today = new Date();
//             const start = new Date();
//             start.setDate(today.getDate() - days);

//             startInput.value = formatDate(start);
//             endInput.value = formatDate(today);
//             form.submit();
//         });
//     });

//     // Clear filters
//     clearBtn.addEventListener("click", () => {
//         startInput.value = "";
//         endInput.value = "";
//         form.querySelector('select[name="producer"]').value = "";
//         form.querySelector( 'select[name="status"]').value = "";
//         form.submit();
//     });
// });

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("filtersForm");
    if (!form) return;

    const startInput = form.querySelector('input[name="start_date"]');
    const endInput = form.querySelector('input[name="end_date"]');
    const producerSelect = form.querySelector('select[name="producer"]');
    const statusSelect = form.querySelector('select[name="status"]');

    const filterBtn = document.getElementById("applyFilters");
    const clearBtn = document.getElementById("clearFilters");
    const rangeButtons = document.querySelectorAll(".quick-range");

    // Format date to YYYY-MM-DD
    function formatDate(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    // -------------------------------
    // APPLY FILTER BUTTON
    // -------------------------------
    filterBtn.addEventListener("click", (e) => {
        e.preventDefault();
        form.submit();
    });

    // -------------------------------
    // QUICK RANGE BUTTONS
    // -------------------------------
    rangeButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();

            const days = parseInt(btn.dataset.range, 10);
            const today = new Date();
            const start = new Date();
            start.setDate(today.getDate() - days);

            startInput.value = formatDate(start);
            endInput.value = formatDate(today);

            form.submit();
        });
    });

    // -------------------------------
    // CLEAR FILTERS
    // -------------------------------
    clearBtn.addEventListener("click", (e) => {
        e.preventDefault();

        startInput.value = "";
        endInput.value = "";
        if (producerSelect) producerSelect.value = "";
        if (statusSelect) statusSelect.value = "";

        form.submit();
    });
});