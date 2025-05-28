// frontend/static/main.js

document.addEventListener("DOMContentLoaded", () => {
  const socket = io("http://localhost:5000");

  const trafficCtx = document.getElementById("trafficChart").getContext("2d");
  const classCtx   = document.getElementById("classChart").getContext("2d");

  const trafficChart = new Chart(trafficCtx, {
    type: "line",
    data: { labels: [], datasets: [{ label: "Anomaly Score", data: [] }] },
    options: { scales: { y: { beginAtZero: true } } },
  });

  const classChart = new Chart(classCtx, {
    type: "bar",
    data: { labels: ["Normal","DDoS"], datasets: [{ label: "Count", data: [0,0] }] },
    options: { scales: { y: { beginAtZero: true } } },
  });

  document.getElementById("normalBtn").onclick = () =>
    socket.emit("simulate", { type: "normal" });
  document.getElementById("ddosBtn").onclick = () =>
    socket.emit("simulate", { type: "ddos" });

  socket.on("update", (msg) => {
    const t = new Date().toLocaleTimeString();
    // update traffic
    trafficChart.data.labels.push(t);
    trafficChart.data.datasets[0].data.push(msg.anomaly_score);
    if (trafficChart.data.labels.length > 20) {
      trafficChart.data.labels.shift();
      trafficChart.data.datasets[0].data.shift();
    }
    trafficChart.update();

    // update count
    classChart.data.datasets[0].data[msg.prediction]++;
    classChart.update();

    // log
    const log = document.getElementById("log");
    log.innerHTML =
      `[${t}] ${msg.sim_data.protocol_type.toUpperCase()} → ` +
      `${msg.prediction === 1 ? "DDoS" : "Normal"} (score ${msg.anomaly_score.toFixed(3)})<br>` +
      log.innerHTML;
  });

  socket.on("error", (err) => {
    const log = document.getElementById("log");
    log.innerHTML = `<span style="color:red">ERROR: ${err.message}</span><br>` + log.innerHTML;
  });
});
