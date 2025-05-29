# backend/app.py

import os
import time
import csv
import random
import logging
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from prometheus_client import start_http_server

from prometheus_metrics import TOTAL_REQUESTS, CLASSIFICATIONS, CURRENT_RATE
from simulator import generate_normal, generate_ddos
from utils import extract_features, classify
from db_setup import init_db, RequestLog

# ─── Logging Setup ───────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ─── Paths ───────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.abspath(os.path.join(BASE, "..", "frontend"))
CSV_LOG = os.path.join(BASE, "predictions.csv")

# Ensure CSV exists
if not os.path.exists(CSV_LOG):
    with open(CSV_LOG, "w", newline="") as f:
        csv.writer(f).writerow([
            "timestamp","traffic_type","duration","protocol_type",
            "src_bytes","dst_bytes","xgb_pred","iso_score","label","count"
        ])

# ─── Flask + Socket.IO Setup ─────────────────────────────────────────
app = Flask(__name__,
    static_folder=os.path.join(FRONTEND, "static"),
    template_folder=os.path.join(FRONTEND, "templates"))
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── DB Session ───────────────────────────────────────────────────────
Session = init_db()

# ─── Background State ──────────────────────────────────────────────────
_last_time = time.time()
_counter = 0
_running = False
_current_type = None

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("start")
def on_start(data):
    global _running, _current_type
    _running = True
    _current_type = data.get("type", "normal")
    logging.info(f">>> STARTED {_current_type.upper()} TRAFFIC")
    emit("status", {"running": True, "type": _current_type})

@socketio.on("stop")
def on_stop():
    global _running
    _running = False
    logging.info(">>> STOPPED TRAFFIC")
    emit("status", {"running": False})

def background_thread():
    global _last_time, _counter
    while True:
        socketio.sleep(0.5)
        if not _running:
            continue

        # 1) Decide how many requests this tick
        if _current_type == "normal":
            count = random.randint(5, 10)
        else:
            count = random.randint(5000, 10000)
        _counter += count

        # 2) Generate one sample and classify if normal, else force
        sim_data = generate_normal() if _current_type == "normal" else generate_ddos()
        TOTAL_REQUESTS.labels(traffic_type=_current_type).inc(count)

        if _current_type == "normal":
            feats = extract_features(sim_data)
            xgb_pred, iso_score = classify(feats)
            label = "DDoS" if (xgb_pred == 1 or iso_score < 0) else "Normal"
        else:
            xgb_pred, iso_score = 1, -1.0
            label = "DDoS"
        CLASSIFICATIONS.labels(result=label).inc(count)

        logging.info(f"[{_current_type.upper()}] count={count} → label={label}")

        # 3) Log to DB
        session = Session()
        try:
            rec = RequestLog(traffic_type=_current_type,
                             features=str(sim_data),
                             classification=label)
            session.add(rec)
            session.commit()
        finally:
            session.close()

        # 4) Append to CSV
        with open(CSV_LOG, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.utcnow().isoformat(),
                _current_type,
                sim_data["duration"],
                sim_data["protocol_type"],
                sim_data["src_bytes"],
                sim_data["dst_bytes"],
                xgb_pred,
                iso_score,
                label,
                count
            ])

        # 5) Update RPS
        now = time.time()
        elapsed = now - _last_time
        if elapsed >= 1.0:
            rps = _counter / elapsed
            CURRENT_RATE.set(rps)
            _counter, _last_time = 0, now
        else:
            rps = CURRENT_RATE._value.get()

        # 6) Emit full payload
        socketio.emit("update", {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "sim_data": sim_data,
            "label": label,
            "xgb_pred": xgb_pred,
            "iso_score": iso_score,
            "count": count,
            "rate": round(rps, 2)
        })

if __name__ == "__main__":
    start_http_server(8000)
    logging.info("Prometheus metrics on port 8000")
    socketio.start_background_task(background_thread)
    socketio.run(app, host="0.0.0.0", port=5000)
