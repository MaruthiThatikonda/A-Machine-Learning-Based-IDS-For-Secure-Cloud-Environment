// analysis.js
document.addEventListener("DOMContentLoaded", () => {
  // Helper function to render a chart
  function renderChart(canvasId, type, data, options) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    new Chart(ctx, { type, data, options });
  }

  // Fetch all metrics data from our new API endpoint
  fetch("/api/metrics_data")
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Network error: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Metrics data received:", data);

      if (data.status !== "ok") {
        document.getElementById(
          "topIps"
        ).innerHTML = `<li>Error: ${data.status ||
          data.message}</li><li>Please run the replay on the Prediction page to generate data.</li>`;
        return;
      }

      // 1. Top-K IPs & Summary Metrics
      const statsList = document.getElementById("topIps");
      statsList.innerHTML = ""; // Clear
      
      data.top_ips.forEach((item) => {
        statsList.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center">
          <b>${item.ip}</b>
          <span class="badge bg-danger rounded-pill">${item.count} alerts</span>
        </li>`;
      });
      
      // Add other stats
      const metrics = data.basic_metrics;
      statsList.innerHTML += `<hr class="my-3">`;
      statsList.innerHTML += `<li class="list-group-item"><b>Total Flows Logged</b>: ${data.count}</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>Accuracy</b>: ${(metrics.accuracy * 100).toFixed(2)}%</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>Precision</b>: ${(metrics.precision * 100).toFixed(2)}%</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>Recall (TPR)</b>: ${(metrics.recall * 100).toFixed(2)}%</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>F1-Score</b>: ${(metrics.f1 * 100).toFixed(2)}%</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>False Positive Rate</b>: ${(data.fpr * 100).toFixed(2)}%</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>Avg. Latency</b>: ${data.avg_latency.toFixed(2)} ms</li>`;
      statsList.innerHTML += `<li class="list-group-item"><b>Throughput</b>: ${data.throughput_est.toFixed(1)} flows/sec</li>`;

      // 2. Confusion Matrix
      const cm = data.confusion_matrix;
      renderChart(
        "confMatrix",
        "bar",
        {
          labels: ["True Neg", "False Pos", "False Neg", "True Pos"],
          datasets: [
            {
              label: "Flows",
              data: [cm.tn, cm.fp, cm.fn, cm.tp],
              backgroundColor: [
                "rgba(40, 167, 69, 0.7)",  // Green
                "rgba(255, 193, 7, 0.7)",  // Yellow/Orange
                "rgba(220, 53, 69, 0.7)",  // Red
                "rgba(0, 123, 255, 0.7)", // Blue
              ],
            },
          ],
        },
        {
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        }
      );

      // 3. ROC Curve
      const rocPoints = data.roc_data.fpr.map((fpr, i) => ({
        x: fpr,
        y: data.roc_data.tpr[i],
      }));
      renderChart(
        "rocChart",
        "scatter",
        {
          datasets: [
            {
              label: "ROC Curve",
              data: rocPoints,
              showLine: true,
              borderColor: "blue",
              backgroundColor: "rgba(0, 0, 255, 0.1)",
              fill: false,
            },
            {
              label: 'Random Chance',
              data: [{x: 0, y: 0}, {x: 1, y: 1}],
              showLine: true,
              borderColor: 'grey',
              borderDash: [5, 5],
              fill: false,
              pointRadius: 0
            }
          ],
        },
        {
          scales: {
            x: {
              title: { display: true, text: "False Positive Rate" },
              min: 0, max: 1
            },
            y: { 
              title: { display: true, text: "True Positive Rate" },
              min: 0, max: 1
            },
          },
        }
      );

      // 4. PR Curve
      const prPoints = data.pr_data.recall.map((rec, i) => ({
        x: rec,
        y: data.pr_data.precision[i],
      }));
      renderChart(
        "prChart",
        "scatter",
        {
          datasets: [
            {
              label: "PR Curve",
              data: prPoints,
              showLine: true,
              borderColor: "purple",
              backgroundColor: "rgba(128, 0, 128, 0.1)",
              fill: false,
            },
          ],
        },
        {
          scales: {
            x: { title: { display: true, text: "Recall" }, min: 0, max: 1 },
            y: { title: { display: true, text: "Precision" }, min: 0, max: 1 },
          },
        }
      );
    })
    .catch((err) => {
      console.error("Failed to fetch metrics:", err);
      document.getElementById(
        "topIps"
      ).innerHTML = `<li>Error loading analytics: ${err.message}</li>`;
    });
});