// Eurotarde - Dashboard Charts

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadPaymentsChart();
});

async function loadStats() {
    try {
        const resp = await fetch('/api/charts/user-stats');
        const data = await resp.json();
        document.getElementById('stat-users').textContent = data.total_users || 0;
        document.getElementById('stat-draws').textContent = data.total_draws || 0;
        document.getElementById('stat-prizes').textContent = formatCurrency(data.total_prizes_paid || 0);
        if (document.getElementById('stat-payments')) {
            document.getElementById('stat-payments').textContent = formatCurrency(data.total_prizes_paid || 0);
        }
    } catch (e) {
        console.error('Error loading stats:', e);
    }
}


async function loadPaymentsChart() {
    try {
        const resp = await fetch('/api/charts/payment-history');
        const data = await resp.json();
        const ctx = document.getElementById('paymentsChart');
        if (!ctx) return;

        const labels = data.map(d => d.month);
        const values = data.map(d => d.total);

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Pagamentos (€)',
                    data: values,
                    fill: true,
                    backgroundColor: 'rgba(0, 51, 102, 0.1)',
                    borderColor: 'rgba(0, 51, 102, 1)',
                    borderWidth: 2,
                    pointBackgroundColor: 'rgba(255, 215, 0, 1)',
                    pointBorderColor: 'rgba(0, 51, 102, 1)',
                    pointRadius: 5,
                    tension: 0.3,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString('pt-PT') + ' €';
                            }
                        }
                    }
                }
            }
        });
    } catch (e) {
        console.error('Error loading payments chart:', e);
    }
}

function formatCurrency(value) {
    return new Intl.NumberFormat('pt-PT', {
        style: 'currency',
        currency: 'EUR'
    }).format(value);
}
