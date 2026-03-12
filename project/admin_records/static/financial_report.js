document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("filtersForm");
    if (!form) return;

    const startInput = form.querySelector('input[name="start_date"]');
    const endInput = form.querySelector('input[name="end_date"]');
    const clearBtn = document.getElementById("clearFilters");
    const rangeButtons = document.querySelectorAll(".quick-range");

    function formatDate(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    rangeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const days = parseInt(btn.dataset.range, 10);
            const today = new Date();
            const start = new Date();
            start.setDate(today.getDate() - days);

            startInput.value = formatDate(start);
            endInput.value = formatDate(today);
            form.submit();
        });
    });

    clearBtn.addEventListener("click", () => {
        startInput.value = "";
        endInput.value = "";
        form.querySelector('select[name="producer"]').value = "";
        form.querySelector('select[name="status"]').value = "";
        form.submit();
    });
});