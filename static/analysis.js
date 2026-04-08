// analysis.js — NIDS Analysis Dashboard (Updated for metrics.json from train.py)

// === Fetch training metrics ===
async function fetchMetrics() {
  try {
    const res = await fetch("/static/data/metrics.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    console.log("✅ Metrics loaded:", data);
    return data.basic_metrics ? data.basic_metrics : data;
  } catch (err) {
    console.error("❌ Failed to load metrics.json:", err);
    showError("Could not load training metrics.");
    return null;
  }
}

// === Error display helper ===
function showError(msg) {
  const box = document.createElement("div");
  box.textContent = msg;
  Object.assign(box.style, {
    position: "fixed",
    bottom: "15px",
    right: "15px",
    background: "rgba(255,0,0,0.25)",
    border: "1px solid rgba(255,100,100,0.6)",
    padding: "10px 16px",
    borderRadius: "10px",
    color: "#fff",
    fontSize: "0.9rem",
    zIndex: 9999,
  });
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 5000);
}

// === Update metric cards ===
function updateCards(m) {
  const fix = (val) =>
    val !== undefined && !isNaN(val) ? (val * 100).toFixed(2) + "%" : "—";
  document.getElementById("accVal").textContent = fix(m.accuracy);
  document.getElementById("precVal").textContent = fix(m.precision);
  document.getElementById("recVal").textContent = fix(m.recall);
  document.getElementById("f1Val").textContent = fix(m.f1);
}

// === Render Confusion Matrix ===
function renderConfMatrix(ctx, cm) {
  if (!cm || !Array.isArray(cm)) return;
  const tn = cm[0][0],
    fp = cm[0][1],
    fn = cm[1][0],
    tp = cm[1][1];

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["True Negative", "False Positive", "False Negative", "True Positive"],
      datasets: [
        {
          label: "Count",
          data: [tn, fp, fn, tp],
          backgroundColor: [
            "rgba(0,200,255,0.6)",
            "rgba(255,80,80,0.6)",
            "rgba(255,180,0,0.6)",
            "rgba(0,255,150,0.6)",
          ],
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: { color: "#ccc" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#ccc" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

// === Render ROC Curve ===
function renderROCCurve(ctx, roc) {
  if (!roc || !roc.fpr || !roc.tpr) return;
  new Chart(ctx, {
    type: "line",
    data: {
      labels: roc.fpr,
      datasets: [
        {
          label: "ROC Curve",
          data: roc.tpr,
          borderColor: "#00e0ff",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#00e0ff" } } },
      scales: {
        x: {
          title: { display: true, text: "False Positive Rate", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          title: { display: true, text: "True Positive Rate", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

// === Render Precision–Recall Curve ===
function renderPRCurve(ctx, pr) {
  if (!pr || !pr.precision || !pr.recall) return;
  new Chart(ctx, {
    type: "line",
    data: {
      labels: pr.recall,
      datasets: [
        {
          label: "Precision–Recall Curve",
          data: pr.precision,
          borderColor: "#8a2be2",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#8a2be2" } } },
      scales: {
        x: {
          title: { display: true, text: "Recall", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          title: { display: true, text: "Precision", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

// === Render Top Features (Feature Importance) ===
function renderTopFeatures(ctx, features) {
  if (!features || features.length === 0) {
    const c = ctx.getContext("2d");
    c.font = "14px Poppins";
    c.fillStyle = "#888";
    c.fillText("No feature importance data found.", 10, 40);
    return;
  }

  const labels = features.map((f) => f.feature);
  const scores = features.map((f) => f.importance);

  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Feature Importance",
          data: scores,
          backgroundColor: "rgba(0,224,255,0.7)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          title: { display: true, text: "Importance", color: "#ccc" },
          ticks: { color: "#ccc" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: { color: "#ccc" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

// === Initialize everything ===
window.addEventListener("DOMContentLoaded", async () => {
  const data = await fetchMetrics();
  if (!data) return;

  updateCards(data);
  renderConfMatrix(document.getElementById("cmChart"), data.confusion_matrix);
  renderROCCurve(document.getElementById("rocChart"), data.roc_data);
  renderPRCurve(document.getElementById("prChart"), data.pr_data);
  renderTopFeatures(document.getElementById("featuresChart"), data.top_features);
});
