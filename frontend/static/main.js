document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  let tick = 0.0;
  let rlEnabled = true;

  // Setup charts
  const anomalyCtx = document.getElementById("anomalyChart").getContext("2d");
  const anomalyChart = new Chart(anomalyCtx, {
    type: "line",
    data: { datasets: [{ label: "Anomaly Score", data: [], borderColor: "#ffab00", fill: false }] },
    options: {
      scales: {
        x: { type: "linear", title: { display: true, text: "Time (s)" }, ticks: { stepSize: 0.5 }, min: 0 },
        y: { beginAtZero: true }
      }
    }
  });

  const classCtx = document.getElementById("classChart").getContext("2d");
  const classChart = new Chart(classCtx, {
    type: "bar",
    data: {
      labels: ["Normal","DDoS"],
      datasets: [{ label: "Count", data: [0,0], backgroundColor: ["#2e7d32","#c62828"] }]
    },
    options: { scales: { y: { beginAtZero: true } } }
  });

  const rateCtx = document.getElementById("rateChart").getContext("2d");
  const rateChart = new Chart(rateCtx, {
    type: "line",
    data: {
      datasets: [
        { label: "Requests/Tick", data: [], borderColor: "#29b6f6", fill: false },
        { label: "Req/sec",      data: [], borderColor: "#ab47bc", fill: false }
      ]
    },
    options: {
      scales: {
        x: { type: "linear", title: { display: true, text: "Time (s)" }, ticks: { stepSize: 0.5 }, min: 0 },
        y: { beginAtZero: true }
      }
    }
  });

  // Controls binding
  document.getElementById("startNormal").onclick = () => socket.emit("start", { type: "normal" });
  document.getElementById("startDdos").onclick   = () => socket.emit("start", { type: "ddos" });
  document.getElementById("stop").onclick        = () => socket.emit("stop");
  document.getElementById("neutralize").onclick  = () => socket.emit("neutralize");
  document.getElementById("toggleRL").onclick    = () => {
    rlEnabled = !rlEnabled;
    socket.emit("toggle_rate_limit", { enabled: rlEnabled });
    document.getElementById("toggleRL").textContent = rlEnabled ? "Disable Rate Limit" : "Enable Rate Limit";
  };

  const tbody = document.getElementById("detailsBody");
  tbody.addEventListener("click", (e) => {
    if (e.target.classList.contains("blockBtn")) {
      const ip = e.target.dataset.ip;
      socket.emit("block_ip", { ip });
      e.target.disabled = true;
      e.target.textContent = "Blocked";
    }
  });

  // Receive updates
  socket.on("update", (msg) => {
    tick = Math.round((tick + 0.5) * 10) / 10;

    // Anomaly
    anomalyChart.data.datasets[0].data.push({ x: tick, y: msg.iso_score });
    anomalyChart.update();

    // Classification
    const idx = msg.label === "DDoS" ? 1 : 0;
    classChart.data.datasets[0].data[idx] += msg.allowed || msg.count;
    classChart.update();

    // Rate & Requests
    rateChart.data.datasets[0].data.push({ x: tick, y: msg.count });
    rateChart.data.datasets[1].data.push({ x: tick, y: msg.rate });
    rateChart.update();

    // Table
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${tick.toFixed(1)}</td>
      <td>${msg.sim_data.protocol_type.toUpperCase()}</td>
      <td>${msg.sim_data.src_bytes}</td>
      <td>${msg.sim_data.dst_bytes}</td>
      <td>${msg.label}</td>
      <td>${msg.iso_score.toFixed(3)}</td>
      <td>${msg.count}</td>
      <td>${msg.rate}</td>
      <td>
        <button class="blockBtn" data-ip="${msg.sim_data.src_ip}">Block IP</button>
      </td>
    `;
    tbody.prepend(row);
    if (tbody.children.length > 10) tbody.removeChild(tbody.lastChild);
  });
});
