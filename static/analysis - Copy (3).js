// ============================================================================
//  analysis.js — Realtime ML Analysis Dashboard (Neon Theme)
//  Compatible with analysis.html & Flask /api/metrics_data endpoint
// ============================================================================

// === Fetch Data from Backend =================================================
async function fetchAnalysisData() {
  try {
    const response = await fetch("/api/metrics_data");
    if (!response.ok) throw new Error("API Error: " + response.status);
    const data = await response.json();
    console.log("✅ Metrics fetched:", data);
    return data;
  } catch (err) {
    console.error("❌ Failed to load analysis data:", err);
    showError("Could not connect to backend. Check Flask server.");
    return null;
  }
}

// === Error Display ===========================================================
function showError(msg) {
  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.bottom = "10px";
  container.style.right = "10px";
  container.style.background = "rgba(255,0,0,0.2)";
  container.style.border = "1px solid red";
  container.style.padding = "10px 15px";
  container.style.borderRadius = "10px";
  container.style.color = "#fff";
  container.style.fontSize = "0.9rem";
  container.style.zIndex = 1000;
  container.textContent = msg;
  document.body.appendChild(container);
  setTimeout(() => container.remove(), 5000);
}

// === Metric Cards ============================================================
function updateMetricCards(metrics) {
  if (metrics.accuracy)
    document.getElementById("accVal").textContent = (metrics.accuracy * 100).toFixed(2) + "%";
  if (metrics.precision)
    document.getElementById("precVal").textContent = (metrics.precision * 100).toFixed(2) + "%";
  if (metrics.recall)
    document.getElementById("recVal").textContent = (metrics.recall * 100).toFixed(2) + "%";
  if (metrics.f1)
    document.getElementById("f1Val").textContent = (metrics.f1 * 100).toFixed(2) + "%";
}

// === Confusion Matrix ========================================================
function renderConfusionMatrix(ctx, cm) {
  const tn = cm.tn ?? cm[0]?.[0] ?? 0;
  const fp = cm.fp ?? cm[0]?.[1] ?? 0;
  const fn = cm.fn ?? cm[1]?.[0] ?? 0;
  const tp = cm.tp ?? cm[1]?.[1] ?? 0;

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Normal", "Attack"],
      datasets: [
        {
          label: "True",
          data: [tn, tp],
          backgroundColor: "rgba(0,224,255,0.6)",
        },
        {
          label: "False",
          data: [fp, fn],
          backgroundColor: "rgba(255,99,132,0.6)",
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: {
          ticks: { color: "#ddd" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#ddd" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: {
        legend: {
          labels: { color: "#00e0ff" },
        },
      },
    },
  });
}

// === ROC Curve ===============================================================
function renderROCCurve(ctx, roc) {
  const fpr = roc.fpr || [];
  const tpr = roc.tpr || [];

  new Chart(ctx, {
    type: "line",
    data: {
      labels: fpr,
      datasets: [
        {
          label: "ROC Curve",
          data: tpr,
          borderColor: "#00e0ff",
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      scales: {
        x: {
          title: { display: true, text: "False Positive Rate", color: "#ccc" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          title: { display: true, text: "True Positive Rate", color: "#ccc" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: {
        legend: { labels: { color: "#00e0ff" } },
      },
    },
  });
}

// === Precision–Recall Curve ==================================================
function renderPRCurve(ctx, pr) {
  const recall = pr.recall || [];
  const precision = pr.precision || [];

  new Chart(ctx, {
    type: "line",
    data: {
      labels: recall,
      datasets: [
        {
          label: "Precision–Recall",
          data: precision,
          borderColor: "#8a2be2",
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      scales: {
        x: {
          title: { display: true, text: "Recall", color: "#ccc" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          title: { display: true, text: "Precision", color: "#ccc" },
          ticks: { color: "#aaa" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: { legend: { labels: { color: "#8a2be2" } } },
    },
  });
}

// === Top Feature Importance ==================================================
function renderTopFeatures(ctx, features) {
  if (!features || features.length === 0) return;
  const labels = features.map(f => f.feature || f.name);
  const scores = features.map(f => f.score || f.importance);

  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Feature Importance",
          data: scores,
          backgroundColor: "rgba(0,224,255,0.6)",
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: "y",
      scales: {
        x: {
          ticks: { color: "#ddd" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: { color: "#ddd" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// === Top IP List =============================================================
function renderTopIPs(ips) {
  const ul = document.getElementById("top-ips");
  ul.innerHTML = "";
  if (!ips || ips.length === 0) {
    ul.innerHTML = "<li>No attack data available</li>";
    return;
  }
  ips.slice(0, 10).forEach((ip) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${ip.ip}</strong> — ${ip.count} attacks`;
    ul.appendChild(li);
  });
}

// === Initialize All ==========================================================
window.addEventListener("DOMContentLoaded", async () => {
  const data = await fetchAnalysisData();
  if (!data) return;

  const metrics = data.basic_metrics || {
    accuracy: data.accuracy,
    precision: data.precision,
    recall: data.recall,
    f1: data.f1,
  };
  const cm = data.confusion_matrix || {};
  const roc = data.roc_data || data.roc_curve || {};
  const pr = data.pr_data || data.pr_curve || {};
  const features = data.top_features || [];
  const ips = data.top_ips || [];

  // Update metric cards
  updateMetricCards(metrics);

  // Render all charts
  renderConfusionMatrix(document.getElementById("cmChart"), cm);
  renderROCCurve(document.getElementById("rocChart"), roc);
  renderPRCurve(document.getElementById("prChart"), pr);
  renderTopFeatures(document.getElementById("featuresChart"), features);
  renderTopIPs(ips);
});
