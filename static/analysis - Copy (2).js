// analysis.js
// ============================================================
// Handles data visualization for Analysis Dashboard
// ============================================================

window.addEventListener("load", function () {
  console.log("📊 Analysis Dashboard Loaded");

  const refreshInterval = 15000; // auto-refresh every 15s

  async function fetchMetrics() {
    try {
      const res = await fetch("/api/metrics_data");
      const data = await res.json();
      if (!data || data.status === "no_data") {
        showMessage("No analysis data available yet. Run a replay first.");
        return;
      }
      renderAll(data);
    } catch (err) {
      console.error("Error loading analytics:", err);
      showMessage(`⚠️ Error loading analytics: ${err.message}`);
    }
  }

  function showMessage(msg) {
    const container = document.getElementById("metrics-container");
    if (container) container.innerHTML = `<p>${msg}</p>`;
  }

  function renderAll(data) {
    renderMetricsCards(data.basic_metrics);
    renderConfusionMatrix(data.confusion_matrix);
    renderTopIPs(data.top_ips);
    renderROC(data.roc_data);
    renderPR(data.pr_data);
    renderTopFeatures(data.top_features);
  }

  // ============================================================
  // 1️⃣ Metrics Summary Cards
  // ============================================================
  function renderMetricsCards(metrics) {
    const accuracy = metrics.accuracy ?? 0;
    const precision = metrics.precision ?? 0;
    const recall = metrics.recall ?? 0;
    const f1 = metrics.f1 ?? 0;

    const cards = document.getElementById("metric-cards");
    if (!cards) return;

    cards.innerHTML = `
      <div class="metric-card bg-green-50 border-l-4 border-green-500">
        <h3>Accuracy</h3>
        <p>${(accuracy * 100).toFixed(2)}%</p>
      </div>
      <div class="metric-card bg-blue-50 border-l-4 border-blue-500">
        <h3>Precision</h3>
        <p>${(precision * 100).toFixed(2)}%</p>
      </div>
      <div class="metric-card bg-orange-50 border-l-4 border-orange-500">
        <h3>Recall</h3>
        <p>${(recall * 100).toFixed(2)}%</p>
      </div>
      <div class="metric-card bg-purple-50 border-l-4 border-purple-500">
        <h3>F1 Score</h3>
        <p>${(f1 * 100).toFixed(2)}%</p>
      </div>
    `;
  }

  // ============================================================
  // 2️⃣ Confusion Matrix
  // ============================================================
  function renderConfusionMatrix(cm) {
    const ctx = document.getElementById("cmChart");
    if (!ctx) return;

    const dataMatrix = [
      [cm.tn || 0, cm.fp || 0],
      [cm.fn || 0, cm.tp || 0],
    ];

    const chartData = {
      labels: ["Predicted Benign", "Predicted Attack"],
      datasets: [
        {
          label: ["Actual Benign"],
          data: [dataMatrix[0][0], dataMatrix[0][1]],
          backgroundColor: ["#4ade80", "#f87171"],
        },
        {
          label: ["Actual Attack"],
          data: [dataMatrix[1][0], dataMatrix[1][1]],
          backgroundColor: ["#60a5fa", "#facc15"],
        },
      ],
    };

    if (window.cmChartInstance) window.cmChartInstance.destroy();
    window.cmChartInstance = new Chart(ctx, {
      type: "bar",
      data: chartData,
      options: {
        responsive: true,
        plugins: {
          legend: { position: "top" },
          title: { display: true, text: "Confusion Matrix" },
        },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  // ============================================================
  // 3️⃣ ROC Curve
  // ============================================================
  function renderROC(roc) {
    const ctx = document.getElementById("rocChart");
    if (!ctx) return;

    if (window.rocChartInstance) window.rocChartInstance.destroy();
    window.rocChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: roc.fpr,
        datasets: [
          {
            label: "ROC Curve",
            data: roc.fpr.map((f, i) => ({ x: f, y: roc.tpr[i] })),
            fill: false,
            borderColor: "rgb(75, 192, 192)",
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "False Positive Rate" } },
          y: { title: { display: true, text: "True Positive Rate" }, min: 0, max: 1 },
        },
      },
    });
  }

  // ============================================================
  // 4️⃣ Precision–Recall Curve
  // ============================================================
  function renderPR(pr) {
    const ctx = document.getElementById("prChart");
    if (!ctx) return;

    if (window.prChartInstance) window.prChartInstance.destroy();
    window.prChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: pr.recall,
        datasets: [
          {
            label: "Precision–Recall Curve",
            data: pr.recall.map((r, i) => ({ x: r, y: pr.precision[i] })),
            fill: false,
            borderColor: "rgb(255, 159, 64)",
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "Recall" } },
          y: { title: { display: true, text: "Precision" }, min: 0, max: 1 },
        },
      },
    });
  }

  // ============================================================
  // 5️⃣ Top Attacking IPs
  // ============================================================
  function renderTopIPs(ips) {
    const container = document.getElementById("top-ips");
    if (!container) return;
    container.innerHTML = "";

    if (!ips || ips.length === 0) {
      container.innerHTML = "<li>No attacking IPs detected yet.</li>";
      return;
    }

    ips.forEach((row) => {
      const li = document.createElement("li");
      li.textContent = `${row.ip} — ${row.count} attacks`;
      container.appendChild(li);
    });
  }

  // ============================================================
  // 6️⃣ Top Features Graph
  // ============================================================
  function renderTopFeatures(features) {
    const ctx = document.getElementById("featuresChart");
    if (!ctx) return;

    if (!features || features.length === 0) {
      ctx.parentElement.innerHTML = "<p>No feature importance data available yet.</p>";
      return;
    }

    const labels = features.slice(0, 5).map((f) => f.feature);
    const scores = features.slice(0, 5).map((f) => f.score);

    if (window.featuresChartInstance) window.featuresChartInstance.destroy();
    window.featuresChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Feature Impact (difference between attack & benign)",
            data: scores,
            backgroundColor: "rgba(255, 99, 132, 0.5)",
            borderColor: "rgb(255, 99, 132)",
            borderWidth: 1.5,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: {
          title: { display: true, text: "Top Features Influencing Attack Decision" },
          legend: { display: false },
        },
        scales: {
          x: { beginAtZero: true },
        },
      },
    });
  }

  // ============================================================
  // Auto Refresh Setup
  // ============================================================
  fetchMetrics();
  setInterval(fetchMetrics, refreshInterval);
});
