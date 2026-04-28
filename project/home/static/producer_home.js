document.addEventListener("DOMContentLoaded", function () {
    const chartElement = document.getElementById("orderStatusChart");
    if (!chartElement) return;

    // Initial chart (all time)
    let chart = new Chart(chartElement, {
        type: 'doughnut',
        data: {
            labels: ['Pending', 'Completed', 'Cancelled'],
            datasets: [{
                data: [
                    chartDataAll.pending,
                    chartDataAll.completed,
                    chartDataAll.cancelled
                ],
                backgroundColor: ['#39a396', '#778da9', '#1b263b'],
                borderWidth: 1
            }]
        },
        options: {
            plugins: { legend: { position: 'bottom' } }
        }
    });

    // Button handlers
    document.getElementById("chart30Btn")?.addEventListener("click", () => {
        chart.data.datasets[0].data = [
            chartData30.pending,
            chartData30.completed,
            chartData30.cancelled
        ];
        chart.update();
    });

    document.getElementById("chartAllBtn")?.addEventListener("click", () => {
        chart.data.datasets[0].data = [
            chartDataAll.pending,
            chartDataAll.completed,
            chartDataAll.cancelled
        ];
        chart.update();
    });

    document.getElementById("chart30Btn")?.addEventListener("click", (e) => {
        setActive(e.target);
        chart.data.datasets[0].data = [
            chartData30.pending,
            chartData30.completed,
            chartData30.cancelled
        ];
        chart.update();
    });

    document.getElementById("chartAllBtn")?.addEventListener("click", (e) => {
        setActive(e.target);
        chart.data.datasets[0].data = [
            chartDataAll.pending,
            chartDataAll.completed,
            chartDataAll.cancelled
        ];
        chart.update();
    });
});

function setActive(btn) {
    document.getElementById("chart30Btn").classList.remove("chart-toggle-active");
    document.getElementById("chartAllBtn").classList.remove("chart-toggle-active");
    btn.classList.add("chart-toggle-active");
}