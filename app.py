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

# ─── Paths & CSV Log Setup ───────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
FRONTEND  = os.path.abspath(os.path.join(BASE, "..", "frontend"))
CSV_LOG   = os.path.join(BASE, "predictions.csv")
if not os.path.exists(CSV_LOG):
    with open(CSV_LOG, "w", newline="") as f:
        csv.writer(f).writerow([
          "timestamp","traffic_type","src_ip","duration","protocol_type",
          "src_bytes","dst_bytes","xgb_pred","iso_score","label","count","allowed","dropped"
        ])

# ─── Flask & Socket.IO Setup ─────────────────────────────────────────
app      = Flask(__name__,
                 static_folder=os.path.join(FRONTEND, "static"),
                 template_folder=os.path.join(FRONTEND, "templates"))
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

Session = init_db()

# ─── State ────────────────────────────────────────────────────────────
_last_time   = time.time()
_counter     = 0
_running     = False
_current_type= None
_neutralized = False
# IP blocking
blocked_ips  = set()
# Rate limiting token bucket
bucket_capacity = 1000
tokens          = bucket_capacity
refill_rate     = 200  # tokens/sec
_last_refill    = time.time()

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("start")
def on_start(data):
    global _running, _current_type, _neutralized
    _running     = True
    _current_type= data.get("type","normal")
    _neutralized = False
    logging.info(f">>> STARTED {_current_type.upper()} traffic")
    emit("status", {"running":True, "type":_current_type})

@socketio.on("stop")
def on_stop():
    global _running
    _running = False
    logging.info(">>> STOPPED traffic")
    emit("status", {"running":False})

@socketio.on("neutralize")
def on_neutralize():
    global _neutralized
    if _current_type=="ddos":
        _neutralized=True
        emit("status",{"neutralized":True})
    else:
        emit("status",{"neutralized":False})

@socketio.on("block_ip")
def on_block_ip(data):
    ip = data.get("ip")
    if ip:
        blocked_ips.add(ip)
        emit("status",{"blocked":list(blocked_ips)})

@socketio.on("toggle_rate_limit")
def on_toggle_rl(data):
    global refill_rate
    enabled = data.get("enabled",False)
    refill_rate = 0 if not enabled else 200
    emit("status",{"rate_limit":enabled})

def background_thread():
    global _last_time, _counter, tokens, _last_refill
    while True:
        socketio.sleep(0.5)
        if not _running: continue

        # Refill tokens
        now = time.time()
        tokens = min(bucket_capacity, tokens + (now - _last_refill)*refill_rate)
        _last_refill = now

        # Decide count
        if _current_type=="normal" or _neutralized:
            count = random.randint(5,10)
        else:
            count = random.randint(5000,10000)
        _counter += count

        # Simulate one request’s data
        sim = generate_normal() if (_current_type=="normal" or _neutralized) else generate_ddos()
        # Assign a random source IP
        sim_ip = random.choice([f"10.0.0.{i}" for i in range(2,255)])
        sim["src_ip"] = sim_ip

        # IP blocking
        if sim_ip in blocked_ips:
            allowed = 0
        else:
            # Rate limiting
            allowed = min(count, int(tokens))
            tokens -= allowed
        dropped = count - allowed

        TOTAL_REQUESTS.labels(traffic_type=_current_type).inc(allowed)

        # Classification (force DDoS if attack & not neutralized)
        if _current_type=="normal" or _neutralized:
            feats = extract_features(sim)
            xgb_pred, iso_score = classify(feats)
            label = "DDoS" if (xgb_pred==1 or iso_score<0) else "Normal"
        else:
            xgb_pred, iso_score, label = 1, -1.0, "DDoS"
        CLASSIFICATIONS.labels(result=label).inc(allowed)

        logging.info(f"[{_current_type.upper()}] IP={sim_ip} count={count} allowed={allowed} dropped={dropped} → {label}")

        # DB & CSV log
        session = Session()
        session.add(RequestLog(traffic_type=_current_type, features=str(sim), classification=label))
        session.commit()
        session.close()
        with open(CSV_LOG,"a",newline="") as f:
            csv.writer(f).writerow([
                datetime.utcnow().isoformat(),
                _current_type, sim_ip,
                sim["duration"], sim["protocol_type"], sim["src_bytes"], sim["dst_bytes"],
                xgb_pred, iso_score, label,
                count, allowed, dropped
            ])

        # RPS
        elapsed = now - _last_time
        if elapsed>=1.0:
            rps = _counter/elapsed
            CURRENT_RATE.set(rps)
            _counter, _last_time = 0, now
        else:
            rps = CURRENT_RATE._value.get()

        socketio.emit("update", {
            "tick": round((_last_time - now)*2)/2,
            "sim_data": sim,
            "label": label,
            "xgb_pred": xgb_pred,
            "iso_score": iso_score,
            "count": count,
            "allowed": allowed,
            "dropped": dropped,
            "rate": round(rps,2)
        })

if __name__=="__main__":
    start_http_server(8000)
    socketio.start_background_task(background_thread)
    socketio.run(app, host="0.0.0.0", port=5000)
