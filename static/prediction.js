// prediction.js
// ==========================================================
// Handles all real-time dashboard logic for NIDS demo
// - Socket.IO streaming
// - Live map visualization
// - Attack rate chart (last 60 seconds)
// - Replay & threshold controls
// ==========================================================

// Ensure all dependencies are loaded
window.addEventListener("load", function () {
  console.log("🌐 prediction.js loaded successfully.");

  // --- Socket.IO Connection ---
  const socket = io.connect(window.location.origin);
  const feed = document.getElementById("live-feed");

  function logToFeed(message, type = "info") {
    if (!feed) return;
    const line = document.createElement("div");
    line.textContent = message;
    line.style.marginBottom = "4px";
    switch (type) {
      case "alert":
        line.style.color = "red";
        line.style.fontWeight = "bold";
        break;
      case "warn":
        line.style.color = "orange";
        break;
      case "success":
        line.style.color = "green";
        break;
      default:
        line.style.color = "#333";
    }
    feed.appendChild(line);
    feed.scrollTop = feed.scrollHeight;
  }

  socket.on("connect", () => {
    console.log("🟢 Connected to Flask-SocketIO server");
    logToFeed("✅ Connected to server.", "success");
  });

  socket.on("disconnect", () => {
    console.warn("🔴 Disconnected from server");
    logToFeed("⚠️ Disconnected from server. Reconnecting...", "warn");
  });

  socket.on("connect_error", (err) => {
    console.error("❌ Socket connection error:", err);
    logToFeed("❌ Connection error. Please refresh.", "warn");
  });

  socket.on("error", (data) => {
    console.error("⚠️ Server error:", data.message);
    logToFeed(`⚠️ SERVER ERROR: ${data.message}`, "warn");
  });

  // ==========================================================
  // Leaflet Map Setup
  // ==========================================================
  let map;
  const mapElement = document.getElementById("map");
  if (mapElement) {
    try {
      map = L.map("map").setView([20, 0], 2);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        minZoom: 2,
        maxZoom: 18,
      }).addTo(map);
      console.log("🗺️ Map initialized.");
    } catch (e) {
      console.error("Map init failed:", e);
    }
  } else {
    console.warn("Map element not found. Skipping map rendering.");
  }

  // ==========================================================
  // Attack Rate Chart Setup
  // ==========================================================
  let attackRateChart;
  let attackData = {
    labels: Array(60).fill(""),
    datasets: [
      {
        label: "Attacks/sec",
        data: Array(60).fill(0),
        borderColor: "rgba(255, 99, 132, 1)",
        backgroundColor: "rgba(255, 99, 132, 0.3)",
        borderWidth: 1.5,
        fill: true,
        tension: 0.4,
      },
    ],
  };

  let attackCountPerSecond = 0;

  const chartCanvas = document.getElementById("attackRateChart");
  if (chartCanvas) {
    try {
      const ctx = chartCanvas.getContext("2d");
      attackRateChart = new Chart(ctx, {
        type: "line",
        data: attackData,
        options: {
          scales: {
            y: { beginAtZero: true, suggestedMax: 10 },
            x: { ticks: { display: false } },
          },
          plugins: { legend: { display: false } },
          maintainAspectRatio: false,
          animation: false,
        },
      });

      console.log("📈 Attack rate chart initialized.");

      // Update chart every second
      setInterval(() => {
        attackData.datasets[0].data.shift();
        attackData.datasets[0].data.push(attackCountPerSecond);
        if (attackRateChart) attackRateChart.update("none");
        attackCountPerSecond = 0; // reset
      }, 1000);
    } catch (e) {
      console.error("Chart init failed:", e);
    }
  }

  // ==========================================================
  // SocketIO Event: Flow Results
  // ==========================================================
  socket.on("flow_result", (data) => {
    const isAttack = data.label === 1;
    const score = data.attack_score ? data.attack_score.toFixed(3) : "N/A";
    const src = data.src_ip || "Unknown";
    const dst = data.dst_ip || "Unknown";

    // Build readable message
    let logMsg = `[${src} → ${dst}] Score: ${score}`;
    if (isAttack) {
      logMsg = `🚨 ATTACK DETECTED: ${logMsg}`;
      if (data.shap_explain && Object.keys(data.shap_explain).length > 0) {
        const explain = Object.entries(data.shap_explain)
          .map(([f, v]) => `${f}: ${v.toFixed(2)}`)
          .join(", ");
        logMsg += ` | Reason: {${explain}}`;
      }
      logToFeed(logMsg, "alert");
    } else {
      logToFeed(logMsg, "info");
    }

    // Map plotting
    if (map && data.geo && data.geo.lat && data.geo.lon) {
      try {
        const marker = L.circleMarker([data.geo.lat, data.geo.lon], {
          radius: isAttack ? 6 : 4,
          color: isAttack ? "red" : "green",
          fillColor: isAttack ? "red" : "green",
          fillOpacity: 0.7,
        })
          .addTo(map)
          .bindPopup(
            `<b>${src}</b><br>Score: ${score}<br>${
              isAttack ? "🚨 Attack" : "✅ Benign"
            }`
          );
        if (isAttack) marker.openPopup();
      } catch (e) {
        console.warn("Map marker failed:", e);
      }
    }

    // Attack counter increment
    if (isAttack) attackCountPerSecond += 1;
  });

  // ==========================================================
  // Replay and Threshold Controls
  // ==========================================================
  console.log("Attaching control event listeners...");

  // Replay controls
  const replaySpeedSlider = document.getElementById("replaySpeed");
  const replaySpeedLabel = document.getElementById("replaySpeedLabel");
  const startReplayButton = document.getElementById("startReplay");

  if (replaySpeedSlider && replaySpeedLabel) {
    replaySpeedSlider.addEventListener("input", () => {
      replaySpeedLabel.textContent = replaySpeedSlider.value;
    });
  }

  if (startReplayButton) {
    startReplayButton.addEventListener("click", () => {
      const speed = replaySpeedSlider ? replaySpeedSlider.value : 1.0;
      logToFeed(`▶️ Starting replay at ${speed}x speed...`, "info");
      console.log(`▶️ Replay started at ${speed}x`);
      socket.emit("start_replay", { speed: speed });
    });
  }

  // Threshold & Params Controls
  const alphaSlider = document.getElementById("alpha");
  const betaSlider = document.getElementById("beta");
  const threshSlider = document.getElementById("thresh");
  const alphaLabel = document.getElementById("alphaLabel");
  const betaLabel = document.getElementById("betaLabel");
  const threshLabel = document.getElementById("threshLabel");
  const applyParamsButton = document.getElementById("applyParams");

  function updateLabel(slider, label) {
    if (slider && label) label.textContent = slider.value;
  }

  if (alphaSlider) alphaSlider.addEventListener("input", () => updateLabel(alphaSlider, alphaLabel));
  if (betaSlider) betaSlider.addEventListener("input", () => updateLabel(betaSlider, betaLabel));
  if (threshSlider) threshSlider.addEventListener("input", () => updateLabel(threshSlider, threshLabel));

  if (applyParamsButton) {
    applyParamsButton.addEventListener("click", () => {
      const params = {
        alpha: alphaSlider ? alphaSlider.value : 0.6,
        beta: betaSlider ? betaSlider.value : 0.4,
        thresh: threshSlider ? threshSlider.value : 0.5,
      };
      console.log("🔧 Applying new parameters:", params);
      logToFeed(
        `🔧 Applying params: α=${params.alpha}, β=${params.beta}, T=${params.thresh}`,
        "info"
      );
      socket.emit("set_params", params);
    });
  }

  console.log("✅ All dashboard listeners attached.");
});
