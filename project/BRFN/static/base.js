document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("globalSearchInput");
    if (!searchInput) return;

    searchInput.addEventListener("input", function () {
        const query = this.value.toLowerCase().trim();

        // Find the first table on the page
        const table = document.querySelector("table");
        if (!table) return;

        // Get all rows except the header
        const rows = table.querySelectorAll("tbody tr");

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(query) ? "" : "none";
        });
    });
});