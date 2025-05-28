# backend/app.py

import os
import time
import logging

from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from prometheus_client import start_http_server

from prometheus_metrics import TOTAL_REQUESTS, CLASSIFICATIONS, CURRENT_RATE
from simulator import generate_normal, generate_ddos
from utils import extract_features, classify
from db_setup import init_db, RequestLog

# ─── Logging Setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
TEMPLATE_DIR = os.path.join(FRONTEND_DIR, "templates")

# ─── App + Socket.IO Setup ──────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path="/static",
    template_folder=TEMPLATE_DIR,
)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── Database Session ───────────────────────────────────────────────────────
Session = init_db()  # will create/use backend/database.db

# ─── Metrics Helpers ────────────────────────────────────────────────────────
_last_time = time.time()
_counter = 0

# ─── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("simulate")
def handle_simulate(data):
    global _last_time, _counter
    ttype = data.get("type", "normal")

    # 1) Generate traffic
    sim_data = generate_normal() if ttype == "normal" else generate_ddos()
    TOTAL_REQUESTS.labels(traffic_type=ttype).inc()

    # 2) Classify
    try:
        pred_label, anomaly_score = classify(extract_features(sim_data))
        CLASSIFICATIONS.labels(result=str(pred_label)).inc()
    except Exception as e:
        logging.error(f"Classification failed: {e}")
        emit("error", {"message": str(e)})
        return

    # 3) Log to DB
    session = Session()
    try:
        rec = RequestLog(
            traffic_type=ttype,
            features=str(sim_data),
            classification=str(pred_label),
        )
        session.add(rec)
        session.commit()
    except Exception as e:
        logging.error(f"DB log failed: {e}")
    finally:
        session.close()

    # 4) Update RPS metric
    _counter += 1
    now = time.time()
    elapsed = now - _last_time
    if elapsed >= 1.0:
        CURRENT_RATE.set(_counter / elapsed)
        _counter = 0
        _last_time = now

    # 5) Emit update
    emit(
        "update",
        {
            "sim_data": sim_data,
            "prediction": pred_label,
            "anomaly_score": anomaly_score,
        },
    )


# ─── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Expose Prometheus metrics
    start_http_server(8000)
    logging.info("Prometheus metrics serving on port 8000")

    # Run Flask + Socket.IO server
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting server at 0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port)
