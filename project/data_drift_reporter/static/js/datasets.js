// datasets.js

async function loadDatasets() {
  const res = await fetch("/api/datasets");
  const datasets = await res.json();

  const tbody = document.getElementById("datasets-list-body");

  if (!datasets.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">
      No datasets yet. <a href="/upload-page">Upload one</a> to get started.</td></tr>`;
    return;
  }

  const rows = await Promise.all(
    datasets.map(async (d) => {
      const colsRes = await fetch(`/api/dataset/${d.id}/columns`);
      const colsData = await colsRes.json();
      const colCount = (colsData.columns || []).length;

      return `
        <tr>
          <td>${d.id}</td>
          <td><strong>${d.dataset_name}</strong></td>
          <td>${formatDate(d.upload_date)}</td>
          <td>${d.row_count}</td>
          <td>${colCount}</td>
          <td><a href="/dataset/${d.id}" class="btn btn-sm btn-outline-primary">View</a></td>
        </tr>`;
    })
  );

  tbody.innerHTML = rows.join("");
}

loadDatasets();
