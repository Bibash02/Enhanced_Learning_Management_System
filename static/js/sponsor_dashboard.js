const ctx = document.getElementById('fundDistributionChart');
    if (ctx) {
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: {{ fund_distribution_labels|safe }},
          datasets: [{
            label: 'Fund Distribution',
            data: {{ fund_distribution_data|safe }},
            backgroundColor: [
              '#0d6efd',
              '#198754',
              '#ffc107',
              '#dc3545',
              '#0dcaf0',
              '#6c757d'
            ],
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              position: 'bottom',
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return context.label + ': $' + context.parsed.toFixed(0);
                }
              }
            }
          }
        }
      });
    }