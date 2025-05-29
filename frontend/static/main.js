// frontend/static/main.js

document.addEventListener("DOMContentLoaded", () => {
  const socket = io();

  // Shared tick counter (seconds)
  let tick = 0.0;

  // Create Anomaly Score chart with a linear time axis
  const anomalyCtx = document.getElementById("anomalyChart").getContext("2d");
  const anomalyChart = new Chart(anomalyCtx, {
    type: "line",
    data: {
      datasets: [{
        label: "Anomaly Score",
        data: [],           // will be [{x: 0, y: 0.12}, ...]
        borderColor: "#ffab00",
        showLine: true,
        fill: false
      }]
    },
    options: {
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: "Time (s)" },
          ticks: { stepSize: 0.5 },
          min: 0
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  // Classification bar chart (unchanged)
  const classCtx = document.getElementById("classChart").getContext("2d");
  const classChart = new Chart(classCtx, {
    type: "bar",
    data: {
      labels: ["Normal","DDoS"],
      datasets: [{
        label: "Count",
        data: [0, 0],
        backgroundColor: ["#2e7d32","#c62828"]
      }]
    },
    options: { scales: { y: { beginAtZero: true } } }
  });

  // Requests & Rate chart with two line datasets and linear x axis
  const rateCtx = document.getElementById("rateChart").getContext("2d");
  const rateChart = new Chart(rateCtx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Requests/Tick",
          data: [], 
          borderColor: "#29b6f6",
          fill: false,
        },
        {
          label: "Req/sec",
          data: [],
          borderColor: "#ab47bc",
          fill: false,
        }
      ]
    },
    options: {
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: "Time (s)" },
          ticks: { stepSize: 0.5 },
          min: 0
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  // Controls
  document.getElementById("startNormal").onclick = () => socket.emit("start",{type:"normal"});
  document.getElementById("startDdos").onclick   = () => socket.emit("start",{type:"ddos"});
  document.getElementById("stop").onclick        = () => socket.emit("stop");

  // On each update from backend
  socket.on("update", (msg) => {
    // Advance our tick by 0.5s
    tick = Math.round((tick + 0.5) * 10) / 10;

    // 1) Anomaly
    anomalyChart.data.datasets[0].data.push({ x: tick, y: msg.iso_score });
    anomalyChart.update();

    // 2) Classification counts
    const idx = msg.label === "DDoS" ? 1 : 0;
    classChart.data.datasets[0].data[idx] += msg.count || 1;
    classChart.update();

    // 3) Requests & Rate
    rateChart.data.datasets[0].data.push({ x: tick, y: msg.count });
    rateChart.data.datasets[1].data.push({ x: tick, y: msg.rate });
    rateChart.update();

    // 4) Details table
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
    `;
    const tbody = document.getElementById("detailsBody");
    tbody.prepend(row);
    if (tbody.children.length > 10) tbody.removeChild(tbody.lastChild);
  });
});
