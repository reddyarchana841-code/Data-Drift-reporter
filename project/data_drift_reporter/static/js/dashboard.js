// dashboard.js

async function loadDashboard() {
  const res = await fetch("/api/dashboard");
  const data = await res.json();

  document.getElementById("stat-total-datasets").textContent = data.total_datasets;
  document.getElementById("stat-total-snapshots").textContent = data.total_snapshots;
  document.getElementById("stat-drift-alerts").textContent = data.drift_alerts;

  if (data.latest_report) {
    document.getElementById("stat-latest-level").textContent = data.latest_report.drift_level;
    document.getElementById("stat-latest-name").textContent =
      `Latest: ${data.latest_report.dataset_name}`;
    document.getElementById("latest-report-text").innerText = data.latest_report.report_text;
  } else {
    document.getElementById("stat-latest-level").textContent = "N/A";
  }

  renderDatasetsTable(data.datasets);
  await renderTrendCharts(data.datasets);
}

function renderDatasetsTable(datasets) {
  const tbody = document.getElementById("datasets-table-body");

  if (!datasets.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">
      No datasets yet. <a href="/upload-page">Upload one</a> to get started.</td></tr>`;
    return;
  }

  tbody.innerHTML = datasets
    .map(
      (d) => `
      <tr>
        <td><strong>${d.dataset_name}</strong></td>
        <td>${d.row_count ?? "-"}</td>
        <td>${d.snapshot_count}</td>
        <td>${formatNumber(d.last_drift_score)}%</td>
        <td>${driftBadgeHtml(d.last_drift_level)}</td>
        <td>${formatDate(d.last_snapshot_date)}</td>
        <td><a href="/dataset/${d.id}" class="btn btn-sm btn-outline-primary">View</a></td>
      </tr>`
    )
    .join("");
}

async function renderTrendCharts(datasets) {
  // Aggregate snapshots across all datasets, grouped per dataset, for trend lines.
  const driftDatasets = [];
  const nullDatasets = [];
  const rowDatasets = [];
  let labels = [];

  const colors = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0891b2"];

  for (let i = 0; i < datasets.length; i++) {
    const d = datasets[i];
    const res = await fetch(`/api/snapshots?dataset_id=${d.id}`);
    const snapshots = await res.json();

    if (snapshots.length > labels.length) {
      labels = snapshots.map((s) => new Date(s.snapshot_date).toLocaleDateString());
    }

    const color = colors[i % colors.length];

    driftDatasets.push({
      label: d.dataset_name,
      data: snapshots.map((s) => s.drift_score),
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
    });

    nullDatasets.push({
      label: d.dataset_name,
      data: snapshots.map((s) => s.null_rate),
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
    });

    rowDatasets.push({
      label: d.dataset_name,
      data: snapshots.map((s) => s.row_count),
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
    });
  }

  makeLineChart("driftTrendChart", labels, driftDatasets, "Drift Score (%)");
  makeLineChart("nullRateChart", labels, nullDatasets, "Null Rate (%)");
  makeLineChart("rowCountChart", labels, rowDatasets, "Row Count");
}

function makeLineChart(canvasId, labels, datasets, yLabel) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { display: datasets.length > 1, position: "bottom" } },
      scales: {
        y: { title: { display: true, text: yLabel }, beginAtZero: true },
      },
    },
  });
}

loadDashboard();
