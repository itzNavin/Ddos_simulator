# backend/routes.py
from flask import Blueprint, request, jsonify
from backend.utils import classify_request, log_request
from flask_socketio import emit
from backend.app import socketio

routes = Blueprint("routes", __name__)

@routes.route("/simulate", methods=["POST"])
def simulate_traffic():
    data = request.json
    source_ip = data.get("source_ip", "192.168.1.1")
    request_size = data.get("request_size", 500)
    request_rate = data.get("request_rate", 10)
    method = data.get("method", "GET")

    try:
        # Classify traffic using models
        result = classify_request(source_ip, request_size, request_rate, method)

        # Log to database
        log_request(source_ip, request_size, request_rate, method, result["classification"], result["is_attack"])

        # Emit live data to frontend
        socketio.emit("traffic_update", {
            "source_ip": source_ip,
            "request_size": request_size,
            "request_rate": request_rate,
            "method": method,
            "classification": result["classification"],
            "is_attack": result["is_attack"]
        })

        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
