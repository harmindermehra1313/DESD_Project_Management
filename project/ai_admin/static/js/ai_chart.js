document.addEventListener("DOMContentLoaded", function () {
    const data = window.aiDashboardData;
    if (!data) return;

    // Component Breakdown Chart
    const componentCtx = document.getElementById('componentChart');
    if (componentCtx) {
        new Chart(componentCtx, {
            type: 'doughnut',
            data: {
                labels: data.componentLabels,
                datasets: [{
                    data: data.componentValues,
                    backgroundColor: ['#1b263b', '#415a77', '#778da9'],
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                cutout: '60%'
            }
        });
    }

    // Execution Time Chart
    const execCtx = document.getElementById('executionChart');
    if (execCtx) {
        new Chart(execCtx, {
            type: 'bar',
            data: {
                labels: data.execLabels,
                datasets: [{
                    label: 'Avg Execution Time (ms)',
                    data: data.execValues,
                    backgroundColor: '#39a396'
                }]
            }
        });
    }
});
