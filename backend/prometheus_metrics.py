# backend/prometheus_metrics.py

from prometheus_client import Counter, Gauge

TOTAL_REQUESTS = Counter(
    "total_requests",
    "Total number of simulation requests received",
    ["traffic_type"],
)

CLASSIFICATIONS = Counter(
    "requests_classified",
    "Number of requests classified by the model",
    ["result"],
)

CURRENT_RATE = Gauge(
    "current_request_rate",
    "Current simulated requests per second",
)
