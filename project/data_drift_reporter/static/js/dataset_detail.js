// dataset_detail.js

const datasetId = document.getElementById("dataset-id").dataset.id;

async function loadDatasetDetail() {
  const snapRes = await fetch(`/api/snapshots?dataset_id=${datasetId}`);
  const snapshots = await snapRes.json();

  const reportRes = await fetch(`/api/drift-report/${datasetId}`);
  const reports = await reportRes.json();

  renderStats(snapshots, reports);
  renderCharts(snapshots);
  renderSnapshotHistory(snapshots);
  renderReportHistory(reports);
}

function renderStats(snapshots, reports) {
  const last = snapshots[snapshots.length - 1];

  document.getElementById("d-row-count").textContent = last ? last.row_count : "-";
  document.getElementById("d-null-rate").textContent = last ? `${formatNumber(last.null_rate)}%` : "-";
  document.getElementById("d-drift-score").textContent = last ? `${formatNumber(last.drift_score)}%` : "-";
  document.getElementById("d-snapshot-count").textContent = snapshots.length;

  if (reports.length) {
    document.getElementById("report-text").innerText = reports[0].report_text;
  }
}

function renderCharts(snapshots) {
  const labels = snapshots.map((s) => new Date(s.snapshot_date).toLocaleString());

  makeLineChart("driftChart", labels, [
    { label: "Drift Score (%)", data: snapshots.map((s) => s.drift_score), borderColor: "#f59e0b", backgroundColor: "#f59e0b", tension: 0.3 },
  ]);

  makeLineChart("nullChart", labels, [
    { label: "Null Rate (%)", data: snapshots.map((s) => s.null_rate), borderColor: "#dc2626", backgroundColor: "#dc2626", tension: 0.3 },
  ]);

  makeLineChart("rowChart", labels, [
    { label: "Row Count", data: snapshots.map((s) => s.row_count), borderColor: "#2563eb", backgroundColor: "#2563eb", tension: 0.3 },
  ]);
}

function makeLineChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // Destroy existing chart instance if re-rendering
  if (ctx._chartInstance) {
    ctx._chartInstance.destroy();
  }

  ctx._chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderSnapshotHistory(snapshots) {
  const tbody = document.getElementById("snapshot-history-body");

  if (!snapshots.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No snapshots yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = snapshots
    .slice()
    .reverse()
    .map(
      (s) => `
      <tr>
        <td>${formatDate(s.snapshot_date)}</td>
        <td>${s.row_count}</td>
        <td>${formatNumber(s.null_rate)}%</td>
        <td>${formatNumber(s.mean_value)}</td>
        <td>${formatNumber(s.drift_score)}%</td>
      </tr>`
    )
    .join("");
}

function renderReportHistory(reports) {
  const container = document.getElementById("report-history");

  if (!reports.length) {
    container.innerHTML = `<div class="list-group-item text-muted py-3">
      No drift reports yet. Generate a second snapshot to create one.</div>`;
    return;
  }

  container.innerHTML = reports
    .map(
      (r) => `
      <div class="list-group-item">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <strong>${formatDate(r.created_at)}</strong>
          ${driftBadgeHtml(r.drift_level)}
        </div>
        <div style="white-space: pre-line;">${r.report_text}</div>
      </div>`
    )
    .join("");
}

document.getElementById("generate-snapshot-btn").addEventListener("click", async (e) => {
  const btn = e.target;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

  try {
    await fetch(`/api/generate-snapshot/${datasetId}`, { method: "POST" });
    await loadDatasetDetail();
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Generate New Snapshot (same data)';
  }
});

document.getElementById("update-data-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const alertBox = document.getElementById("update-alert");
  alertBox.classList.add("d-none");

  const fileInput = document.getElementById("update-file");
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

  try {
    const res = await fetch(`/api/dataset/${datasetId}/update-data`, { method: "POST", body: formData });
    const data = await res.json();

    if (res.ok) {
      alertBox.className = "alert alert-success";
      alertBox.textContent = "Dataset updated! New snapshot and drift report generated below.";
      alertBox.classList.remove("d-none");
      fileInput.value = "";
      await loadDatasetDetail();
    } else {
      alertBox.className = "alert alert-danger";
      alertBox.textContent = data.error || "Update failed.";
      alertBox.classList.remove("d-none");
    }
  } catch (err) {
    alertBox.className = "alert alert-danger";
    alertBox.textContent = "Update failed: " + err.message;
    alertBox.classList.remove("d-none");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-upload"></i> Upload &amp; Generate New Snapshot';
  }
});

loadDatasetDetail();
