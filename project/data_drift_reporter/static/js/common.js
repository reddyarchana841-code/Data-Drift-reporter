// common.js - shared helper functions

function driftBadgeHtml(level) {
  const cls = {
    Low: "badge-drift-low",
    Medium: "badge-drift-medium",
    High: "badge-drift-high",
  }[level] || "badge-drift-low";

  return `<span class="badge ${cls}">${level || "N/A"}</span>`;
}

function formatDate(isoString) {
  if (!isoString) return "-";
  const d = new Date(isoString);
  return d.toLocaleString();
}

function formatNumber(n, decimals = 2) {
  if (n === null || n === undefined) return "-";
  return Number(n).toFixed(decimals);
}
