// ===============================
//  COLORS (consistent palette)
// ===============================
const COLORS = {
    primary: "#1b263b",
    secondary: "#415a77",
    accent: "#778da9",
    green: "#39a396",
    red: "#d9534f",
    yellow: "#f0ad4e"
};




// ===============================
//  USER GROWTH CHART
// ===============================
const growthData = {
    15: window.adminDashboardData.growth_15,
    30: window.adminDashboardData.growth_30,
    365: window.adminDashboardData.growth_365,
};
// Prevent duplicate charts if JS loads twice
if (window.userChart) {
    window.userChart.destroy();
}
window.userChart = new Chart(document.getElementById("userGrowthChart"), {

    type: "line",
    data: {
        labels: growthData[30].labels,
        datasets: [{
            label: "New Users",
            data: growthData[30].values,
            borderColor: COLORS.primary,
            backgroundColor: "rgba(27,38,59,0.2)",
            borderWidth: 2,
            tension: 0.3,
            fill: true
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { display: false }
        }
    }
});

// ===============================
//  FILTER BUTTONS
// ===============================
document.querySelectorAll(".chart-filter").forEach(btn => {
    btn.addEventListener("click", () => {
        const range = btn.dataset.range;
        const d = growthData[range];

        // Update chart data
        window.userChart.data.labels = d.labels;
        window.userChart.data.datasets[0].data = d.values;
        window.userChart.update();


        // Update title
        const title = document.getElementById("growthTitle");
        if (range === "15") title.textContent = "User Growth (Last 15 Days)";
        if (range === "30") title.textContent = "User Growth (Last 30 Days)";
        if (range === "365") title.textContent = "User Growth (Last 12 Months)";
    });
});

// ===============================
//  ACCOUNT TYPE BREAKDOWN
// ===============================
new Chart(document.getElementById("accountTypeChart"), {
    type: "doughnut",
    data: {
        labels: window.adminDashboardData.accountTypeLabels,
        datasets: [{
            data: window.adminDashboardData.accountTypeValues,
            backgroundColor: [COLORS.primary, COLORS.secondary, COLORS.accent]
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
    }
});

// ===============================
//  ACCOUNT STATUS
// ===============================
new Chart(document.getElementById("accountStatusChart"), {
    type: "doughnut",
    data: {
        labels: window.adminDashboardData.accountStatusLabels,
        datasets: [{
            data: window.adminDashboardData.accountStatusValues,
            backgroundColor: [COLORS.green, COLORS.red]
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
    }
});

// ===============================
//  PRODUCT STATUS
// ===============================
new Chart(document.getElementById("productStatusChart"), {
    type: "bar",
    data: {
        labels: window.adminDashboardData.productStatusLabels,
        datasets: [{
            label: "Products",
            data: window.adminDashboardData.productStatusValues,
            backgroundColor: [COLORS.primary, COLORS.yellow, COLORS.red]
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true }
        }
    }
});

// ===============================
//  REVIEW SENTIMENT
// ===============================
new Chart(document.getElementById("reviewSentimentChart"), {
    type: "pie",
    data: {
        labels: window.adminDashboardData.reviewSentimentLabels,
        datasets: [{
            data: window.adminDashboardData.reviewSentimentValues,
            backgroundColor: [COLORS.green, COLORS.yellow, COLORS.red]
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
    }
});
